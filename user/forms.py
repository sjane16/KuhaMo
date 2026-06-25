from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from .models import Report

def get_location_choices():
    choices = [('', 'Select a location')]

    MAIN_BUILDING = [
        # Floor 1 — offices
        ('MB_lobby', 'MB | Lobby'),
        ('MB_clinic', 'MB | Clinic'),
        ('MB_guidance', 'MB | Guidance Office'),
        ('MB_finance', 'MB | Finance Office'),
        ('MB_registrar', 'MB | Registrar'),
        ('MB_cashier', 'MB | Cashier'),
        ('MB_chapel', 'MB | Chapel'),
        # Floor 2 — rooms + offices
        ('MB_201', 'M201'),
        ('MB_202', 'M202'),
        ('MB_203', 'M203'),
        ('MB_204', 'M204'),
        ('MB_205', 'M205'),
        ('MB_faculty', 'MB | Faculty Room'),
        ('MB_dean', 'MB | Dean\'s Office'),
        ('MB_conference', 'MB | Conference Room'),
        # Floor 3 — Amba Wing + offices
        ('MB_301', 'Amba M301'),
        ('MB_302', 'Amba M302'),
        ('MB_303', 'Amba M303'),
        ('MB_304', 'Amba M304'),
        ('MB_305', 'Amba M305'),
        ('MB_306', 'Amba M306'),
        ('MB_307', 'Amba M307'),
        ('MB_avr', 'MB | AVR'),
        ('MB_storage', 'MB | Storage Room'),
        # Floor 4
        ('MB_401', 'M401'),
        ('MB_402', 'M402'),
        ('MB_403', 'M403'),
        ('MB_404', 'M404'),
        ('MB_405', 'M405'),
        ('MB_server', 'MB | Server Room'),
        ('MB_cict', 'MB | CICT Office'),
    ]

    NEW_BUILDING = [
        # Floor 1 — offices
        ('NB_lobby', 'NB | Lobby'),
        ('NB_security', 'NB | Security Office'),
        ('NB_canteen', 'NB | Canteen'),
        ('NB_bookstore', 'NB | Bookstore'),
        # Floor 2
        ('NB_201', 'NB201'),
        ('NB_202', 'NB202'),
        ('NB_203', 'NB203'),
        ('NB_204', 'NB204'),
        ('NB_205', 'NB205'),
        ('NB_toilet_male_2', 'NB | Male Toilet Floor 2'),
        ('NB_toilet_female_2', 'NB | Female Toilet Floor 2'),
        ('NB_hallway_2', 'NB | Hallway Floor 2'),
        # Floor 3
        ('NB_301', 'NB301'),
        ('NB_302', 'NB302'),
        ('NB_303', 'NB303'),
        ('NB_304', 'NB304'),
        ('NB_305', 'NB305'),
        ('NB_toilet_male_3', 'NB | Male Toilet Floor 3'),
        ('NB_toilet_female_3', 'NB | Female Toilet Floor 3'),
        ('NB_hallway_3', 'NB | Hallway Floor 3'),
        # Floor 4
        ('NB_401', 'NB401'),
        ('NB_402', 'NB402'),
        ('NB_403', 'NB403'),
        ('NB_404', 'NB404'),
        ('NB_405', 'NB405'),
        ('NB_toilet_male_4', 'NB | Male Toilet Floor 4'),
        ('NB_toilet_female_4', 'NB | Female Toilet Floor 4'),
        ('NB_hallway_4', 'NB | Hallway Floor 4'),
    ]

    LLB = [
        # Floor 1
        ('LLB_library', 'LLB | Library'),
        ('LLB_reading', 'LLB | Reading Area'),
        ('LLB_librarian', 'LLB | Librarian Office'),
        # Floor 2
        ('LLB_lab1', 'LLB | Electronics Lab'),
        ('LLB_lab2', 'LLB | Lab 2'),
        ('LLB_lab3', 'LLB | Lab 3'),
    ]

    choices += MAIN_BUILDING + NEW_BUILDING + LLB
    return choices

class ReportForm(forms.ModelForm):
    location = forms.ChoiceField(choices=get_location_choices)
    photo = forms.ImageField(required=True)

    class Meta:
        model = Report
        fields = ['photo', 'category', 'location', 'description']


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['department', 'phone']

class ProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['profile_photo']
    