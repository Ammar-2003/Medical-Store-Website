from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

class Medicine(models.Model):
    DISCOUNT_CHOICES = [
        ('percent', 'Percentage (%)'),
        ('flat', 'Flat Amount (Rs)'),
    ]

    name = models.CharField(max_length=100)
    company = models.CharField(max_length=100)
    formula = models.CharField(
        max_length=100,
        blank=True,
        null=False,
        default='',
        verbose_name="Chemical Formula"
    )
    batch_no = models.CharField(
        blank=True,
        null=False,
        default='',
        verbose_name="Batch No",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0
    )
    retailers_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        verbose_name="Purchase Price (Rs)"
    )
    packet_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        verbose_name="Selling Price per Packet (Rs)"
    )
    units_per_box = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=1,
        verbose_name="Units per Packet"
    )
    rack_number = models.CharField(max_length=20)
    expiry_date = models.DateField()

    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_CHOICES,
        default='percent'
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0
    )

    stock = models.PositiveIntegerField(default=0, verbose_name="Current Stock")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def purchase_per_unit_price(self):
        if self.units_per_box:
            return round(self.retailers_price / self.units_per_box, 2)
        return 0

    @property
    def selling_per_unit_price(self):
        if self.units_per_box:
            return round(self.packet_price / self.units_per_box, 2)
        return 0

    def clean(self):
        if self.discount_type == 'flat' and self.discount > self.packet_price:
            raise ValidationError("Flat discount cannot exceed the price of the packet.")

        if self.expiry_date and self.expiry_date < now().date():
            raise ValidationError("Expiry date cannot be in the past.")

        if self.units_per_box and self.packet_price:
            self.price = self.packet_price / self.units_per_box

    @property
    def calculated_discount(self):
        return (self.price * self.discount) / 100 if self.discount_type == 'percent' else self.discount

    @property
    def selling_price(self):
        return self.price - self.calculated_discount

    def get_discount_display(self):
        return f"{self.discount}%" if self.discount_type == 'percent' else f"₹{self.discount}"

    @property
    def is_expired(self):
        return self.expiry_date < now().date()

    @property
    def is_expiring_soon(self):
        if self.stock <= 0 or self.is_expired:  # Explicitly exclude expired and out-of-stock
            return False
        threshold = now().date() + timedelta(days=120)
        return self.expiry_date <= threshold

    @property
    def total_purchased(self):
        return sum(purchase.quantity for purchase in self.purchases.all())

    @property
    def total_purchase_amount(self):
        return sum(purchase.total_amount for purchase in self.purchases.all())

    @property
    def last_purchase(self):
        return self.purchases.order_by('-purchase_date').first()


class PurchaseRecord(models.Model):
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='purchases'
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-purchase_date']
        verbose_name_plural = "Purchase Records"

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # Update medicine stock when purchase is created
        if not self.pk:  # Only on creation
            self.medicine.stock += self.quantity
            self.medicine.save()