from django import forms
from .models import Medicine, PurchaseRecord
from django.core.exceptions import ValidationError
from django.utils import timezone

class MedicineAddForm(forms.ModelForm):
    initial_stock = forms.IntegerField(
        label='Initial Stock Quantity',
        min_value=1,
        required=True,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter initial stock amount'
        })
    )
    
    purchase_note = forms.CharField(
        label='Purchase Note (Optional)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Initial stock purchase'
        })
    )

    class Meta:
        model = Medicine
        fields = [
            'name', 'company', 'formula', 'retailers_price', 
            'packet_price', 'units_per_box', 'rack_number', 
            'expiry_date', 'discount_type', 'discount', 'batch_no'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Panadol 500mg',
                'class': 'form-control'
            }),
            'formula': forms.TextInput(attrs={
                'placeholder': 'C8H9NO2',
                'class': 'form-control'
            }),
            'retailers_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'packet_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'units_per_box': forms.NumberInput(attrs={
                'class': 'form-control'
            }),
            'batch_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter batch number'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Manufacturer name'
            }),
            'rack_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Rack A-12'
            }),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'discount_type': forms.RadioSelect(choices=Medicine.DISCOUNT_CHOICES),
            'discount': forms.NumberInput(attrs={
                'min': '0', 
                'class': 'form-control'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        initial_stock = cleaned_data.get('initial_stock', 0)
        
        if initial_stock <= 0:
            raise ValidationError("Initial stock must be at least 1.")
            
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Record initial purchase
            initial_stock = self.cleaned_data.get('initial_stock', 0)
            unit_price = instance.retailers_price / instance.units_per_box if instance.units_per_box else 0
            
            PurchaseRecord.objects.create(
                medicine=instance,
                quantity=initial_stock,
                unit_price=unit_price,
                total_amount=initial_stock * unit_price,
                notes=self.cleaned_data.get('purchase_note', 'Initial stock purchase')
            )
            
            # Update stock
            instance.stock = initial_stock
            instance.save()
        
        return instance


class MedicineUpdateForm(forms.ModelForm):
    additional_stock = forms.IntegerField(
        label='Additional Stock Quantity',
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter amount to add'
        })
    )
    
    purchase_note = forms.CharField(
        label='Purchase Note (Optional)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Additional stock purchase'
        })
    )
    
    current_stock = forms.IntegerField(
        label='Current Stock',
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'
        })
    )
    
    future_stock = forms.IntegerField(
        label='Future Stock (Preview)',
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control bg-light',
            'readonly': 'readonly'
        })
    )

    class Meta:
        model = Medicine
        fields = [
            'name', 'company', 'formula', 'retailers_price', 
            'packet_price', 'units_per_box', 'rack_number', 
            'expiry_date', 'discount_type', 'discount', 'batch_no'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self.initial['current_stock'] = self.instance.stock
            self.initial['future_stock'] = self.instance.stock

    def clean(self):
        cleaned_data = super().clean()
        additional_stock = cleaned_data.get('additional_stock', 0)
        
        # Update future stock preview
        if self.instance and self.instance.pk:
            cleaned_data['future_stock'] = self.instance.stock + additional_stock
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        additional_stock = self.cleaned_data.get('additional_stock', 0)
        
        if commit:
            instance.save()
            
            if additional_stock > 0:
                # Record additional purchase
                unit_price = instance.retailers_price / instance.units_per_box if instance.units_per_box else 0
                
                PurchaseRecord.objects.create(
                    medicine=instance,
                    quantity=additional_stock,
                    unit_price=unit_price,  # Using direct calculation instead of property
                    total_amount=additional_stock * unit_price,
                    notes=self.cleaned_data.get('purchase_note', 'Additional stock purchase')
                )
                
                # Update stock
                instance.stock += additional_stock
                instance.save()
        
        return instance
