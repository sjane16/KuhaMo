from pathlib import Path

from django import forms


class ManualSurveySubmissionForm(forms.Form):
    scan_file = forms.ImageField(label='Scanned Job Order (JPG or PNG)')
    quality = forms.IntegerField(min_value=1, max_value=5)
    quantity = forms.IntegerField(min_value=1, max_value=5)
    timeliness = forms.IntegerField(min_value=1, max_value=5)

    def clean_scan_file(self):
        image = self.cleaned_data['scan_file']
        if Path(image.name).suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            raise forms.ValidationError('Upload a JPG or PNG image.')
        if image.size > 10 * 1024 * 1024:
            raise forms.ValidationError('The scanned Job Order must be 10 MB or smaller.')
        return image
