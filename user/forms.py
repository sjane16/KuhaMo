from django import forms
from .models import Report

def get_location_choices():
    choices = [('', 'Select a location')]
    for floor in range(2, 5):
        for room in range(1, 11):
            room_number = floor * 100 + room
            if 301 <= room_number <= 307:
                label = f'Amba Wing | rm {room_number}'
            else:
                label = f'rm {room_number}'
            choices.append((str(room_number), label))
    return choices

class ReportForm(forms.ModelForm):
    location = forms.ChoiceField(choices=get_location_choices)
    photo = forms.ImageField(required=True)

    class Meta:
        model = Report
        fields = ['photo', 'category', 'location', 'description']