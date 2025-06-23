# forms.py
from django import forms
from .models import PaybackConsumable, ConsumableRequest, User

class PaybackForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=True)

    class Meta:
        model = PaybackConsumable
        fields = ['user', 'consumable_request', 'amount_paid', 'repayment_date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'user' in self.data:
            try:
                user_id = int(self.data.get('user'))
                self.fields['consumable_request'].queryset = ConsumableRequest.objects.filter(
                    user_id=user_id, status__in=['Approved', 'Pending']
                )
            except (ValueError, TypeError):
                pass
        else:
            self.fields['consumable_request'].queryset = ConsumableRequest.objects.none()
