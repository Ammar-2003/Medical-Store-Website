from django import forms
from .models import Return, ReturnItem
from decimal import Decimal

class ReturnForm(forms.ModelForm):
    class Meta:
        model = Return
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Enter reason for return...'
            }),
        }

class ReturnItemForm(forms.ModelForm):
    restock = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Restock item'
    )
    
    class Meta:
        model = ReturnItem
        fields = ['quantity', 'restock']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control return-quantity',
                'min': '1',
                'step': '1'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.sale_item = kwargs.pop('sale_item', None)
        super().__init__(*args, **kwargs)
        
        if self.sale_item:
            max_quantity = self.sale_item.net_quantity
            self.fields['quantity'].widget.attrs['max'] = max_quantity
            self.fields['quantity'].help_text = f'Max available: {max_quantity}'
            
            # Set initial returned_price based on unit price
            if 'quantity' in self.initial:
                self.initial['returned_price'] = (
                    Decimal(str(self.sale_item.unit_price)) * 
                    Decimal(str(self.initial['quantity'])))
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if self.sale_item and quantity > self.sale_item.net_quantity:
            raise forms.ValidationError(
                f'Cannot return more than {self.sale_item.net_quantity} items'
            )
        return quantity