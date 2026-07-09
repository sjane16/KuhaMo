from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from .models import Report
from adm.models import Building, Floor, Room

class ReportForm(forms.ModelForm):
    building = forms.ModelChoiceField(queryset=Building.objects.all(), empty_label="Select a Building", required=True)
    floor = forms.ModelChoiceField(queryset=Floor.objects.none(), empty_label="Select a Floor", required=True)
    location = forms.ModelChoiceField(queryset=Room.objects.none(), empty_label="Select a Room", required=True)
    photo = forms.ImageField(required=True)

    class Meta:
        model = Report
        fields = ['photo', 'category', 'custom_category', 'location', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        tailwind_classes = 'w-full appearance-none border border-gray-200 rounded-xl px-4 py-3.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer pr-10'
        self.fields['building'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_building'})
        self.fields['floor'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_floor'})
        self.fields['location'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_location'})
        self.fields['category'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_category'})
        self.fields['custom_category'].widget.attrs.update({'class': 'w-full border border-gray-200 rounded-xl px-4 py-3.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent', 'id': 'id_custom_category'})

        if 'building' in self.data:
            try:
                building_id = int(self.data.get('building'))
                self.fields['floor'].queryset = Floor.objects.filter(building_id=building_id).order_by('floor_number')
            except (ValueError, TypeError):
                pass

        if 'floor' in self.data:
            try:
                floor_id = int(self.data.get('floor'))
                self.fields['location'].queryset = Room.objects.filter(floor_id=floor_id).order_by('name')
            except (ValueError, TypeError):
                pass

        #For adding styling lang, there's another installing if we used wigdet pa eh. (will update nalang).
        tailwind_classes = 'w-full appearance-none border border-gray-200 rounded-xl px-4 py-3.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer pr-10' 
        self.fields['building'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_building'})
        self.fields['floor'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_floor'})
        self.fields['location'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_location'})
        self.fields['category'].widget.attrs.update({'class': tailwind_classes, 'id': 'id_category'})
        self.fields['custom_category'].widget.attrs.update({'class': 'w-full border border-gray-200 rounded-xl px-4 py-3.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent', 'id': 'id_custom_category'})

        #For Catching Errors and Validationzzz
        if 'building' in self.data:
            try:
                building_id = int(self.data.get('building'))
                self.fields['floor'].queryset = Floor.objects.filter(building_id=building_id).order_by('floor_number')
            except (ValueError, TypeError):
                pass
        
        if 'floor' in self.data:
            try:
                floor_id = int(self.data.get('floor'))
                self.fields['location'].queryset=Room.objects.filter(floor_id=floor_id).order_by('name')
            except (ValueError, TypeError):
                pass

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

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo:
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Profile photo size should not exceed 5MB.")
        return photo