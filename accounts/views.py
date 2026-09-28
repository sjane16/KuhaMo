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
from user.models import UserProfile
import random
import string
from django.core.mail import send_mail
from django.conf import settings 
from django.utils import timezone
from django.db import transaction
from smtplib import SMTPException

def _clear_messages(request):
    storage = get_messages(request)
    storage.used = True


def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))

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
                   request.session['pending_login_backend'] = user.backend

                   
                   otp = _generate_otp()
                   UserProfile.objects.update_or_create(
                       user=user,
                       defaults={
                           'otp': otp,
                           'otp_created_at': timezone.now()
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

           expiry_minutes = 10
           is_expired = (timezone.now() - profile.otp_created_at).total_seconds() > expiry_minutes * 60

           if is_expired:
               _clear_messages(request)
               messages.error(request, "Your code has expired. Please request a new one.")
           elif submitted_otp == profile.otp:
                profile.otp = ''
                profile.save()
                del request.session['pending_login_user_id']

                user.backend = request.session.pop('pending_login_backend', 'django.contrib.auth.backends.ModelBackend')
                login(request, user)

                if user.is_staff or user.is_superuser:
                    return redirect('/adm/dashboard/')
                return redirect('/user/user_dashboard/')
           else:
               _clear_messages(request)
               messages.error(request, "Invalid verification code. Please try again.")
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
            'otp_created_at': timezone.now()
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

@never_cache
def signup(request):
    if request.method == 'POST':
       ip = request.META.get('REMOTE_ADDR')

       if is_ip_flagged(ip):
           _clear_messages(request)
           messages.error(request, "Unable to process your request. Please contact system administrator")

           return render(request, 'accounts/signup.html', {'form': SignUpForm()})

       if request.POST.get('website'):
           _log_honeypot(request)
           _clear_messages(request)
           messages.error(request, "Unable to process your request. Please contact system administrator")

           return render(request, 'accounts/signup.html', {'form': SignUpForm()})

       if is_ratelimited(request, key='ip', rate='5/m', method='POST', increment=True, fn=signup):
           messages.error(request, "Too many signup attempts. Please try again later")
           return render(request, 'accounts/signup.html', {'form': SignUpForm()})

       form = SignUpForm(request.POST)
       if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            role = form.cleaned_data['role']
            department = form.cleaned_data['department']
            phone = form.cleaned_data['phone']

            try:
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
                            'otp_created_at': timezone.now()
                        }
                    )

                    send_mail(
                        subject='Your OTP for Account Verification',
                        message=f'Your verification code is: {otp}\n This code will expire in 10 minutes. Please do not share this code with anyone.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
            except (SMTPException, OSError) as e:
                _clear_messages(request)
                messages.error(request, "We couldn't send your verification email right now. Please try again in a moment.")
                return render(request, 'accounts/signup.html', {'form': form})

            request.session['pending_verification_user_id'] = user.id
            _clear_messages(request)
            messages.success(request, "Account created successfully! Please check your email for the verification code to verify your account.")
            return redirect('verify_otp')
       else:
           print(form.errors)
           _clear_messages(request)
           messages.error(request, "Please fill up all required fields correctly")
    else:
        initial = {}
        if request.session.get('privacy_accepted'):
            initial['agree_to_terms'] = True
        form = SignUpForm(initial=initial)

    return render(request, 'accounts/signup.html', {'form': form})

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

           expiry_minutes = 10
           is_expired = (timezone.now() - profile.otp_created_at).total_seconds() > expiry_minutes * 60

           if is_expired:
               _clear_messages(request)
               messages.error(request, "Your code has expired. Please request a new verification code.")
           elif submitted_otp == profile.otp:
                user.is_active = True
                user.save()
                profile.otp = ''
                profile.save()
                del request.session['pending_verification_user_id']
                _clear_messages(request)
                messages.success(request, "Your account has been verified successfully! You can now log in.")
                return redirect('login')
           else:
               _clear_messages(request)
               messages.error(request, "Invalid verification code. Please try again.")
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
            'otp_created_at': timezone.now()
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
                    'otp_created_at': timezone.now()
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

            expiry_minutes = 10
            is_expired = (timezone.now() - profile.otp_created_at).total_seconds() > expiry_minutes * 60

            if is_expired:
                _clear_messages(request)
                messages.error(request, "Your code has expired. Please request a new one.")
            elif submitted_otp == profile.otp:
                request.session['password_reset_verified'] = True
                _clear_messages(request)
                return redirect('reset_password')
            else:
                _clear_messages(request)
                messages.error(request, "Invalid verification code. Please try again.")
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
            'otp_created_at': timezone.now()
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
    verified = request.session.get('password_reset_verified')

    if not user_id or not verified:
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
        if form.is_valid():
            new_password = form.cleaned_data['new_password']

            user.set_password(new_password)
            user.save()

            try:
                profile = UserProfile.objects.get(user=user)
                profile.otp = ''
                profile.save()
            except UserProfile.DoesNotExist:
                pass

            del request.session['pending_reset_user_id']
            del request.session['password_reset_verified']

            _clear_messages(request)
            messages.success(request, "Your password has been reset successfully. You can now log in with your new password.")
            return redirect('login')
        else:
            _clear_messages(request)
            messages.error(request, "Please fill up all required fields correctly")
    else:
        form = ResetPasswordForm()

    return render(request, 'accounts/reset_password.html', {'form': form})

@never_cache
def privacy_policy(request):
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

