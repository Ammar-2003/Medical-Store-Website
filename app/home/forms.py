from django import forms

class MedicineSearchForm(forms.Form):
    search_query = forms.CharField(
        required=False,
        label='Search Medicine',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter medicine name and dosage (e.g., Paracetamol 500mg)'
        })
    )