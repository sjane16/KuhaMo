from django import forms 

class StudentLogin(forms.Form):

    student_id = forms.CharField(
        max_length=9,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your student ID',
            'class':'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    student_password = forms.CharField(
        widget= forms.PasswordInput(attrs={
            'id': 'student_password_field',
            'placeholder': 'Enter your password',
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

class AdminLogin(forms.Form):

    admin_id = forms.CharField(
        max_length=9,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your ID',
            'class': 'w-full bg-transparent outline-none text-sm text-slate-700 placeholder-slate-400'
        })
    )

    admin_password = forms.CharField(
        widget= forms.PasswordInput(attrs={
            'id': 'admin_password_field',
            'placeholder': 'Enter your password',
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