from django  import forms

from .models import *


class LoanSettingsForm(forms.ModelForm):
    class Meta:
        model = LoanSettings

        fields = "__all__"