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