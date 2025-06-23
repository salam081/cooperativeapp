# yourapp/forms.py
from django import forms
import datetime

class DistributionForm(forms.Form):
    # Use a MonthField for better user experience and validation
    month = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'month'}),
        label="Select Month to Distribute"
    )

    def clean_month(self):
        # Ensure the selected month is not in the future
        date_selected = self.cleaned_data['month']
        if date_selected.year > datetime.date.today().year or \
           (date_selected.year == datetime.date.today().year and date_selected.month > datetime.date.today().month):
            raise forms.ValidationError("Cannot distribute savings for a future month.")
        return date_selected