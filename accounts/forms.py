from django import forms 
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from user.validators import phone_validator, validate_name, validate_no_gibberish, validate_password_strength
from user.models import UserProfile


def is_unverified_signup(user):
    """True for an account that was created at signup but never verified or used."""
    return not user.is_active and user.last_login is None

class placeholderSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value == '':
            option['attrs']['disabled'] = 'disabled'
        return option

class LoginForm(forms.Form):

    email= forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400',
            'autocomplete': 'username'
        })
    )

    password = forms.CharField(
            widget=forms.PasswordInput(attrs={
                'id': 'login_password',
                'placeholder': 'Enter your password',
                'autocomplete': 'current-password',
                'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
            })
        )

    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'autocomplete': 'off', 'tabindex': '-1'})
    )

    def clean_website(self):
        value = self.cleaned_data.get('website')
        if value:
            raise forms.ValidationError("Something went wrong. Please try again")
        return value

class SignUpForm(forms.Form):

    DEPARTMENT_CHOICES = [('', 'Select your department'), *UserProfile.DEPARTMENT_CHOICES]

    role = forms.ChoiceField(
    choices=[
        ('', 'Select your role'),
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('staff', 'Staff'),
    ],
    widget=placeholderSelect(attrs={
        'class': 'w-full bg-transparent outline-none text-sm text-slate-700 invalid:text-slate-400',
        'required':'required',
        'data-cdd': '',
        'data-cdd-variant': 'transparent',
        'aria-label': 'Role',
    })
)

    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your first name',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your last name',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    department = forms.ChoiceField(
        choices=DEPARTMENT_CHOICES,
        widget=placeholderSelect(attrs={
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 invalid:text-slate-400',
            'required': 'required',
            'data-cdd': '',
            'data-cdd-variant': 'transparent',
            'aria-label': 'Department',
        }),
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    phone = forms.CharField(
        max_length=11,
        # Same behavior as Edit Profile > Contact Number: digits only, 11 max, number keypad on phones
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'inputmode': 'numeric',
            'maxlength': '11',
            'pattern': r'\d{11}',
            'title': 'Phone number must be exactly 11 digits, numbers only',
            'placeholder': '09XXXXXXXXX',
            'autocomplete': 'tel',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'id': 'signup_password',
            'placeholder': 'Enter your password',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'id': 'signup_confirm_password',
            'placeholder': 'Confirm your password',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    agree_to_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 mt-[2px] text-blue-600 rounded border-gray-300 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50'
        }),
        error_messages = {
            'required': 'You must agree to the Terms and Conditions and Privacy Policy to continue'
        }
    )

    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'autocomplete': 'off', 'tabindex': '-1'})
    )

    def clean_website(self):
            value = self.cleaned_data.get('website')
            if value:
                raise forms.ValidationError("Something went wrong. Please try again")
            return value

    def clean_role(self):
         role = self.cleaned_data.get('role')
         if role == '':
              raise forms.ValidationError("Please select a role")
         return role

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        errors = []
        try:
            first_name = validate_name(first_name, field_label="First name")
        except DjangoValidationError as e:
            errors.extend(e.messages)

        errors.extend(validate_no_gibberish(first_name))
        if errors:
            raise forms.ValidationError(errors)
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        errors = []
        try:
            last_name = validate_name(last_name, field_label="Last name")
        except DjangoValidationError as e:
            errors.extend(e.messages)

        errors.extend(validate_no_gibberish(last_name))
        if errors:
            raise forms.ValidationError(errors)

        return last_name

    def clean_department(self):
         department = self.cleaned_data.get('department')
         if department == '':
              raise forms.ValidationError("Please select a department")
         return department

    def clean_phone(self):
     phone = self.cleaned_data.get('phone')
     if phone:
         try:
             phone_validator(phone)
         except DjangoValidationError as e:
             raise forms.ValidationError(e.messages)
     return phone

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        role = self.cleaned_data.get('role')

        if role != 'staff' and not email.endswith('@udm.edu.ph'):
                raise forms.ValidationError(""
                "Users must use their official UDM email address (@udm.edu.ph) except for university personnel"
        )

        existing = User.objects.filter(email=email).first()
        if existing and not is_unverified_signup(existing):
            raise forms.ValidationError("An account with this email already exists")

        return email 

    def clean_password(self):
        # Same rules and messages as Edit Profile > Change Password (user/views.py)
        password = self.cleaned_data.get('password')
        errors = validate_password_strength(password)
        if errors:
            raise forms.ValidationError(errors)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")

        return cleaned_data

class PrivacyAgreementForm(forms.Form):
    agree_to_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 mt-[2px] text-blue-600 rounded border-gray-300 cursor-pointer'
        }),
        error_messages={'required': 'You must agree to the Terms and Conditions and Privacy Policy to continue'}
    )
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'autocomplete': 'off', 'tabindex': '-1'})
    )

    def clean_website(self):
        value = self.cleaned_data.get('website')
        if value:
            raise forms.ValidationError("Something went wrong. Please try again")
        return value

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter the 6-digit OTP',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400 tracking-widest text-center',
            'max_length': '6',
            'autocomplete': 'off',
        })
    )

class ForgotPasswordForm(forms.Form):

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400',
            'autocomplete': 'off'
        })
    )

    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'autocomplete': 'off', 'tabindex': '-1'})
    )

    def clean_website(self):
        value = self.cleaned_data.get('website')
        if value:
            raise forms.ValidationError("Something went wrong. Please try again")
        return value


class ResetPasswordForm(forms.Form):

    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'id': 'reset_new_password',
            'placeholder': 'Enter your new password',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    confirm_new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'id': 'reset_confirm_new_password',
            'placeholder': 'Confirm your new password',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'autocomplete': 'off', 'tabindex': '-1'})
    )

    def clean_website(self):
        value = self.cleaned_data.get('website')
        if value:
            raise forms.ValidationError("Something went wrong. Please try again")
        return value

    def clean_new_password(self):
        # Same rules and messages as Edit Profile > Change Password (user/views.py)
        password = self.cleaned_data.get('new_password')
        errors = validate_password_strength(password)
        if errors:
            raise forms.ValidationError(errors)
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_new_password = cleaned_data.get('confirm_new_password')

        if new_password and confirm_new_password:
            if new_password != confirm_new_password:
                self.add_error('confirm_new_password', "Passwords do not match.")

        return cleaned_data
