from django.shortcuts import render, redirect 
from .forms import LoginForm, SignUpForm, OTPVerificationForm, PrivacyAgreementForm, ForgotPasswordForm, ResetPasswordForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User 
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.contrib.messages import get_messages
from axes.utils import reset_request
from django.core.exceptions import PermissionDenied
from django_ratelimit.core import is_ratelimited
from security.models import HoneypotHit
from security.utils import is_ip_flagged
from security.audit import log_event, LOGIN_PASSWORD_OTP, LOGIN_TRUSTED_DEVICE
from user.models import UserProfile, invalidate_trusted_devices
import secrets
import string
from django.utils.crypto import constant_time_compare
from django.db.models import F
from django.core import signing
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings 
from django.utils import timezone
from django.db import transaction
from smtplib import SMTPException
from django.utils.http import url_has_allowed_host_and_scheme #helps with redirecting users together with the next parameter.

def _clear_messages(request):
    storage = get_messages(request)
    storage.used = True


def _generate_otp():
    return ''.join(secrets.choice(string.digits) for _ in range(6))


RESET_VERIFIED_WINDOW_SECONDS = 10 * 60
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5

# Trusted devices: after a successful OTP, the browser gets a signed cookie
# so MFA is skipped on that device until the window runs out.
ADMIN_MFA_WINDOW = timedelta(days=7)
USER_MFA_WINDOW = timedelta(days=30)
TRUSTED_DEVICE_SALT = 'accounts.trusted_device'

def _is_admin(user):
    return user.is_staff or user.is_superuser

def _mfa_window(user):
    return ADMIN_MFA_WINDOW if _is_admin(user) else USER_MFA_WINDOW

def _trusted_cookie_name(user):
    # One cookie per account, so shared computers don't mix users up
    return f'fc_td_{user.pk}'

def _credentials_version(user):
    # Goes up only on a real password change (invalidate_trusted_devices).
    # Not tied to the password hash, because Django rewrites the hash on login
    # whenever a server with a different Django version checks the password.
    version = UserProfile.objects.filter(user=user).values_list('credentials_version', flat=True).first()
    return version or 0

def _trust_device(response, request, user):
    value = signing.dumps({'u': user.pk, 'v': _credentials_version(user)}, salt=TRUSTED_DEVICE_SALT)
    response.set_cookie(
        _trusted_cookie_name(user),
        value,
        max_age=int(_mfa_window(user).total_seconds()),
        httponly=True,
        secure=request.is_secure(),
        samesite='Lax',
    )
    return response

def _is_trusted_device(request, user):
    raw = request.COOKIES.get(_trusted_cookie_name(user))
    if not raw:
        return False
    try:
        # max_age is checked against the role's window at login time,
        # so a user promoted to admin drops to the 7-day rule right away
        data = signing.loads(raw, salt=TRUSTED_DEVICE_SALT, max_age=_mfa_window(user))
    except signing.BadSignature:  # also covers SignatureExpired
        return False
    return data.get('u') == user.pk and data.get('v') == _credentials_version(user)

def _post_login_redirect(request, user):
    next_url = request.session.pop('pending_login_next', '')
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    if _is_admin(user):
        return redirect('/adm/dashboard/')
    return redirect('/user/user_dashboard/')

def _check_otp(profile, submitted_otp, request=None, purpose=''):
    """
    Check a submitted code against the user's current OTP.
    Returns (status, attempts_left) where status is 'ok', 'invalid', 'locked' or 'expired'.
    Each code allows OTP_MAX_ATTEMPTS guesses, then it's locked until a new one is sent.
    """
    if profile.otp_attempts >= OTP_MAX_ATTEMPTS:
        return 'locked', 0

    if not profile.otp or not profile.otp_created_at:
        return 'expired', 0
    if (timezone.now() - profile.otp_created_at).total_seconds() > OTP_EXPIRY_MINUTES * 60:
        return 'expired', 0

    # Reserve an attempt atomically so parallel requests can't sneak past the limit
    reserved = UserProfile.objects.filter(
        pk=profile.pk, otp_attempts__lt=OTP_MAX_ATTEMPTS
    ).update(otp_attempts=F('otp_attempts') + 1)
    if not reserved:
        return 'locked', 0

    if constant_time_compare(submitted_otp, profile.otp):
        # One-time use: burn the code so it can't be replayed
        profile.otp = ''
        profile.otp_attempts = 0
        profile.save(update_fields=['otp', 'otp_attempts'])
        return 'ok', 0

    profile.refresh_from_db(fields=['otp_attempts'])
    attempts_left = OTP_MAX_ATTEMPTS - profile.otp_attempts
    if attempts_left <= 0:
        # Logged once, on the guess that used up the last attempt
        log_event(request, 'otp_locked', user=profile.user, purpose=purpose)
        return 'locked', 0
    return 'invalid', attempts_left

def _otp_error(request, status, attempts_left):
    _clear_messages(request)
    if status == 'expired':
        messages.error(request, "Your code has expired. Please request a new one.")
    elif status == 'locked':
        messages.error(request, "Too many wrong attempts. This code is now locked. Please request a new one.")
    else:
        plural = '' if attempts_left == 1 else 's'
        messages.error(request, f"Invalid verification code. You have {attempts_left} attempt{plural} left.")

def _clear_reset_session(request):
    for key in ('pending_reset_user_id', 'password_reset_verified_user_id',
                'password_reset_verified_at', 'password_reset_verified'):
        request.session.pop(key, None)

def _log_honeypot(request):
    HoneypotHit.objects.create(
        trigger_type='form_field',
        path=request.path,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        extra_info=f"Bot filled honeypot field with: {request.POST.get('website')}"
    )

def custom_lockout(request, credentials=None, *args, **kwargs):
    _clear_messages(request)
    messages.error(request, "Access denied. Your account has been temporarily locked due to 5 failed login attempts. Please try again after 30 minutes")
    return redirect('login')  


   
@never_cache
def splash_screen(request):
    return render(request, 'accounts/index.html')

@never_cache
def login_view(request):
    # remembers the selected page before directing to login
    if request.method == 'GET':
        next_url = request.GET.get('next', '')

        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()}, #only allows redirects to its host 
            require_https=request.is_secure(),
        ):
            request.session['pending_login_next'] = next_url
        else:
            request.session.pop('pending_login_next', None)

    if request.method == 'POST':
       ip = request.META.get('REMOTE_ADDR')

       if is_ip_flagged(ip):
           _clear_messages(request)
           messages.error(request, "Invalid email or password")
           return render(request, 'accounts/login.html', {'form': LoginForm()})

       if request.POST.get('website'):
           _log_honeypot(request)
           _clear_messages(request)
           messages.error(request, "Invalid email or password")
           return render(request, 'accounts/login.html', {'form': LoginForm()})

       if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=login_view):
           messages.error(request, "Too many login attempts. Please try again later")
           return render(request, 'accounts/login.html', {'form': LoginForm()})

       form = LoginForm(request.POST)
       if form.is_valid():
           email = form.cleaned_data.get('email')
           password = form.cleaned_data.get('password')

           try:
               user = authenticate(request, username=email, password=password)

               if user is not None:
                   if not user.is_active:
                       _clear_messages(request)
                       messages.error(request, "Please verify your email before logging in")
                       return render(request, 'accounts/login.html', {'form': LoginForm()})

                   reset_request(request)

                   if _is_trusted_device(request, user):
                       request.audit_login_method = LOGIN_TRUSTED_DEVICE
                       login(request, user)
                       _clear_messages(request)
                       return _post_login_redirect(request, user)

                   request.session['pending_login_backend'] = user.backend

                   
                   otp = _generate_otp()
                   UserProfile.objects.update_or_create(
                       user=user,
                       defaults={
                           'otp': otp,
                           'otp_created_at': timezone.now(),
                           'otp_attempts': 0
                       }
                   )

                   try:
                       send_mail(
                           subject='Your Fac-Check Login Code',
                           message=f'Your login verification code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
                           from_email=settings.DEFAULT_FROM_EMAIL,
                           recipient_list=[user.email],
                           fail_silently=False,
                       )
                   except (SMTPException, OSError):
                       _clear_messages(request)
                       messages.error(request, "We couldn't send your login code right now. Please try again in a moment.")
                       return render(request, 'accounts/login.html', {'form': LoginForm()})

                   request.session['pending_login_user_id'] = user.id
                   _clear_messages(request)
                   return redirect('verify_login_otp')

               else:
                   _clear_messages(request)
                   messages.error(request, "Invalid email or password")

           except PermissionDenied:
               _clear_messages(request)
               messages.error(request, "Access denied. Your account has been temporarily locked due to 5 failed login attempts. Please try again after 30 minutes")

           except Exception as e:
               _clear_messages(request)
               messages.error(request, "An authentication gateway failure occured. Please contact system administrator")
       else:
           _clear_messages(request)
           messages.error(request, "Please fill up all required fields correctly")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})

@never_cache
def verify_login_otp(request):
    user_id = request.session.get('pending_login_user_id')

    if not user_id:
        messages.error(request, "No pending login found. Please log in again.")
        return redirect('login')

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        messages.error(request, "Invalid login session. Please log in again.")
        return redirect('login')

    if request.method == 'POST':

       if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=verify_login_otp):
           messages.error(request, "Too many verification attempts. Please try again later")
           return render(request, 'accounts/verify_login.html', {'form': OTPVerificationForm(), 'user_email': user.email})

       form = OTPVerificationForm(request.POST)
       if form.is_valid():
           submitted_otp = form.cleaned_data['otp']

           try:
               profile = UserProfile.objects.get(user=user)
           except UserProfile.DoesNotExist:
                _clear_messages(request)
                messages.error(request, "Verification failed. Please log in again.")
                return redirect('login')

           status, attempts_left = _check_otp(profile, submitted_otp, request, 'login')

           if status != 'ok':
               _otp_error(request, status, attempts_left)
           else:
                del request.session['pending_login_user_id']

                user.backend = request.session.pop('pending_login_backend', 'django.contrib.auth.backends.ModelBackend')
                request.audit_login_method = LOGIN_PASSWORD_OTP
                login(request, user)

                return _trust_device(_post_login_redirect(request, user), request, user)
       else:
            _clear_messages(request)
            messages.error(request, "Please enter a valid 6-digit code")
    else:
        form = OTPVerificationForm()

    return render(request, 'accounts/verify_login.html', {'form': form, 'user_email': user.email})


@never_cache
def resend_login_otp(request):
    user_id = request.session.get('pending_login_user_id')

    if not user_id:
        messages.error(request, "No pending login found. Please log in again.")
        return redirect('login')

    if is_ratelimited(request, key='ip', rate='2/m', method='POST', increment=True, fn=resend_login_otp):
        messages.error(request, "Please wait before requesting another code")
        return redirect('verify_login_otp')

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        messages.error(request, "Invalid login session. Please log in again.")
        return redirect('login')

    otp = _generate_otp()
    UserProfile.objects.update_or_create(
        user=user,
        defaults={
            'otp': otp,
            'otp_created_at': timezone.now(),
            'otp_attempts': 0
        }
    )

    try:
        send_mail(
            subject='Your Fac-Check Login Code',
            message=f'Your login verification code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except (SMTPException, OSError):
        messages.error(request, "We couldn't resend your code right now. Please try again in a moment.")
        return redirect('verify_login_otp')

    messages.success(request, "A new login code has been sent to your email.")
    return redirect('verify_login_otp')

def _privacy_viewed(request):
    return bool(request.session.get('privacy_viewed') or request.session.get('privacy_accepted'))

def _render_signup(request, form):
    viewed = _privacy_viewed(request)
    # Until the Privacy Policy page has been opened, the checkbox can't be ticked
    if not viewed:
        form.fields['agree_to_terms'].widget.attrs['disabled'] = True
    return render(request, 'accounts/signup.html', {'form': form, 'privacy_viewed': viewed})

@never_cache
def signup(request):
    if request.method == 'POST':
       ip = request.META.get('REMOTE_ADDR')

       if is_ip_flagged(ip):
           _clear_messages(request)
           messages.error(request, "Unable to process your request. Please contact system administrator")

           return _render_signup(request, SignUpForm())

       if request.POST.get('website'):
           _log_honeypot(request)
           _clear_messages(request)
           messages.error(request, "Unable to process your request. Please contact system administrator")

           return _render_signup(request, SignUpForm())

       if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=signup):
           messages.error(request, "Too many signup attempts. Please try again later")
           return _render_signup(request, SignUpForm())

       form = SignUpForm(request.POST)
       is_valid = form.is_valid()
       if not _privacy_viewed(request):
           # The checkbox is locked on the page, but enforce it here too
           form.add_error('agree_to_terms', "Please open and read the Privacy Policy and Terms of Service before agreeing.")
           is_valid = False

       if is_valid:
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            role = form.cleaned_data['role']
            department = form.cleaned_data['department']
            phone = form.cleaned_data['phone']

            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=False
                )

                otp = _generate_otp()
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        'role': role,
                        'department': department,
                        'phone': phone,
                        'otp': otp,
                        'otp_created_at': timezone.now(),
                        'otp_attempts': 0
                    }
                )

            try:
                send_mail(
                    subject='Your OTP for Account Verification',
                    message=f'Your verification code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except (SMTPException, OSError):
                user.delete()
                _clear_messages(request)
                messages.error(request, "We couldn't send your verification email right now. Please try again in a moment.")
                return _render_signup(request, form)

            request.session['pending_verification_user_id'] = user.id
            _clear_messages(request)
            messages.success(request, "Account created successfully! Please check your email for the verification code to verify your account.")
            return redirect('verify_otp')
       else:
           print(form.errors)
           _clear_messages(request)
    else:
        initial = {}
        if request.session.get('privacy_accepted'):
            initial['agree_to_terms'] = True
        form = SignUpForm(initial=initial)

    return _render_signup(request, form)

@never_cache
def verify_otp(request):
    user_id = request.session.get('pending_verification_user_id')


    if not user_id:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect('signup')

    try:
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        messages.error(request, "Invalid verification session. Please sign up again.")
        return redirect('signup')

    if request.method == 'POST':

       if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=verify_otp):
           messages.error(request, "Too many verification attempts. Please try again later")
           return render(request, 'accounts/verify_otp.html', {'form': OTPVerificationForm(), 'user_email': user.email})

       form = OTPVerificationForm(request.POST)
       if form.is_valid():
           submitted_otp = form.cleaned_data['otp']

           try:
               profile = UserProfile.objects.get(user=user)
           except UserProfile.DoesNotExist:
                _clear_messages(request)
                messages.error(request, "Verification failed. Please sign up again.")
                return redirect('signup')

           status, attempts_left = _check_otp(profile, submitted_otp, request, 'signup verification')

           if status != 'ok':
               _otp_error(request, status, attempts_left)
           else:
                user.is_active = True
                user.save()
                del request.session['pending_verification_user_id']
                _clear_messages(request)
                messages.success(request, "Your account has been verified successfully! You can now log in.")
                # The device that verified the signup is trusted, so the first login skips MFA
                return _trust_device(redirect('login'), request, user)
       else:
            _clear_messages(request)
            messages.error(request, "Please enter a valid 6-digit code")
    else:
        form = OTPVerificationForm()

    return render(request, 'accounts/verify_otp.html', {'form': form, 'user_email': user.email})

@never_cache
def resend_otp(request):
    user_id = request.session.get('pending_verification_user_id')

    if not user_id:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect('signup')

    if is_ratelimited(request, key='ip', rate='2/m', method='POST', increment=True, fn=resend_otp):
        messages.error(request, "Please wait before requesting another code")
        return redirect('verify_otp')

    try:
        user = User.objects.get(id=user_id, is_active=False)
    except User.DoesNotExist:
        messages.error(request, "Invalid verification session. Please sign up again.")
        return redirect('signup')

    otp = _generate_otp()
    UserProfile.objects.update_or_create(
        user=user, 
        defaults={
            'otp': otp, 
            'otp_created_at': timezone.now(),
            'otp_attempts': 0
        }
    )

    send_mail(
                    subject='Your OTP for Account Verification',
                    message=f'Your verification code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

    messages.success(request, "A new verification code has been sent to your email.")
    return redirect('verify_otp')

@never_cache
def forgot_password(request):
    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR')

        if is_ip_flagged(ip):
            _clear_messages(request)
            messages.error(request, "Unable to process your request. Please contact system administrator")
            return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm()})

        if request.POST.get('website'):
            _log_honeypot(request)
            _clear_messages(request)
            messages.error(request, "Unable to process your request. Please contact system administrator")
            return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm()})

        if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=forgot_password):
            messages.error(request, "Too many requests. Please try again later")
            return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm()})

        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email', '').strip().lower()

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                _clear_messages(request)
                messages.error(request, "No account found with that email address")
                return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm()})

            if not user.is_active:
                _clear_messages(request)
                messages.error(request, "Please verify your email before resetting your password")
                return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm()})

            otp = _generate_otp()
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'otp': otp,
                    'otp_created_at': timezone.now(),
                    'otp_attempts': 0
                }
            )

            try:
                send_mail(
                    subject='Your Fac-Check Password Reset Code',
                    message=f'Your password reset code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except (SMTPException, OSError):
                _clear_messages(request)
                messages.error(request, "We couldn't send your reset code right now. Please try again in a moment.")
                return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm()})

            _clear_reset_session(request)
            request.session['pending_reset_user_id'] = user.id
            _clear_messages(request)
            return redirect('verify_reset_otp')
        else:
            _clear_messages(request)
            messages.error(request, "Please enter a valid email address")
    else:
        form = ForgotPasswordForm()

    return render(request, 'accounts/forgot_password.html', {'form': form})


@never_cache
def verify_reset_otp(request):
    user_id = request.session.get('pending_reset_user_id')

    if not user_id:
        messages.error(request, "No pending password reset found. Please try again.")
        return redirect('forgot_password')

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        messages.error(request, "Invalid reset session. Please try again.")
        return redirect('forgot_password')

    if request.method == 'POST':

        if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=verify_reset_otp):
            messages.error(request, "Too many verification attempts. Please try again later")
            return render(request, 'accounts/verify_reset_otp.html', {'form': OTPVerificationForm(), 'user_email': user.email})

        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            submitted_otp = form.cleaned_data['otp']

            try:
                profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                _clear_messages(request)
                messages.error(request, "Verification failed. Please try again.")
                return redirect('forgot_password')

            status, attempts_left = _check_otp(profile, submitted_otp, request, 'password reset')

            if status != 'ok':
                _otp_error(request, status, attempts_left)
            else:
                # Bind verification to THIS user, not just a True flag
                request.session['password_reset_verified_user_id'] = user.id
                request.session['password_reset_verified_at'] = timezone.now().timestamp()
                _clear_messages(request)
                return redirect('reset_password')
        else:
            _clear_messages(request)
            messages.error(request, "Please enter a valid 6-digit code")
    else:
        form = OTPVerificationForm()

    return render(request, 'accounts/verify_reset_otp.html', {'form': form, 'user_email': user.email})


@never_cache
def resend_reset_otp(request):
    user_id = request.session.get('pending_reset_user_id')

    if not user_id:
        messages.error(request, "No pending password reset found. Please try again.")
        return redirect('forgot_password')

    if is_ratelimited(request, key='ip', rate='2/m', method='POST', increment=True, fn=resend_reset_otp):
        messages.error(request, "Please wait before requesting another code")
        return redirect('verify_reset_otp')

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        messages.error(request, "Invalid reset session. Please try again.")
        return redirect('forgot_password')

    otp = _generate_otp()
    UserProfile.objects.update_or_create(
        user=user,
        defaults={
            'otp': otp,
            'otp_created_at': timezone.now(),
            'otp_attempts': 0
        }
    )

    try:
        send_mail(
            subject='Your Fac-Check Password Reset Code',
            message=f'Your password reset code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except (SMTPException, OSError):
        messages.error(request, "We couldn't resend your code right now. Please try again in a moment.")
        return redirect('verify_reset_otp')

    messages.success(request, "A new reset code has been sent to your email.")
    return redirect('verify_reset_otp')


@never_cache
def reset_password(request):
    user_id = request.session.get('pending_reset_user_id')
    verified_user_id = request.session.get('password_reset_verified_user_id')
    verified_at = request.session.get('password_reset_verified_at')

    verification_valid = (
        user_id
        and verified_user_id == user_id
        and verified_at
        and timezone.now().timestamp() - verified_at <= RESET_VERIFIED_WINDOW_SECONDS
    )

    if not verification_valid:
        _clear_reset_session(request)
        messages.error(request, "Please verify your identity before resetting your password.")
        return redirect('forgot_password')

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        messages.error(request, "Invalid reset session. Please try again.")
        return redirect('forgot_password')

    if request.method == 'POST':

        if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=reset_password):
            messages.error(request, "Too many attempts. Please try again later")
            return render(request, 'accounts/reset_password.html', {'form': ResetPasswordForm()})

        if request.POST.get('website'):
            _log_honeypot(request)
            messages.error(request, "Unable to process your request. Please contact system administrator")
            return render(request, 'accounts/reset_password.html', {'form': ResetPasswordForm()})

        form = ResetPasswordForm(request.POST)
        # Same rule as Edit Profile: the new password can't be the current one
        if form.is_valid() and user.check_password(form.cleaned_data['new_password']):
            form.add_error('new_password', "New Password must be different from your current password.")

        if form.is_valid():
            new_password = form.cleaned_data['new_password']

            user.set_password(new_password)
            user.save()
            invalidate_trusted_devices(user)
            log_event(request, 'password_reset', user=user)

            try:
                profile = UserProfile.objects.get(user=user)
                profile.otp = ''
                profile.save()
            except UserProfile.DoesNotExist:
                pass

            _clear_reset_session(request)

            _clear_messages(request)
            messages.success(request, "Your password has been reset successfully. You can now log in with your new password.")
            return redirect('login')
        else:
            # Each specific error is listed on the page, like the signup form
            _clear_messages(request)
    else:
        form = ResetPasswordForm()

    return render(request, 'accounts/reset_password.html', {'form': form})

@never_cache
def privacy_policy(request):
    # Opening this page unlocks the "I agree" checkbox on the signup form
    request.session['privacy_viewed'] = True

    if request.method == 'POST':
        if request.POST.get('website'):
            _log_honeypot(request)
            messages.error(request, "Unable to process your request. Please contact system administrator")
            return redirect('signup')

        form = PrivacyAgreementForm(request.POST)
        if form.is_valid():
            request.session['privacy_accepted'] = True
            return redirect('signup')
        else:
            messages.error(request, "You must agree to the Privacy Policy and Terms of Service to continue")
            return render(request, 'accounts/privacypolicy.html', {'form': form})

    initial = {'agree_to_terms': request.session.get('privacy_accepted', False)}
    form = PrivacyAgreementForm(initial=initial)
    return render(request, 'accounts/privacypolicy.html', {'form': form})

