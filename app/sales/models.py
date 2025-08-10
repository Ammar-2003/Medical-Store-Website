from django.db import models
from django.db.models import Sum , Count
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta , date

class Sale(models.Model):
    # Existing fields remain the same
    id = models.AutoField(primary_key=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    price_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_applied_on_return = models.BooleanField(default=False)
    extra = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # New cached fields for performance
    _net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    _total_profit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    _returned_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['-sale_date']),
        ]

    def save(self, *args, **kwargs):
        # Original final amount calculation remains unchanged
        if not self.final_amount:
            self.final_amount = (
                Decimal(str(self.subtotal)) -
                Decimal(str(self.discount_amount)) -
                Decimal(str(self.price_deducted)) +
                Decimal(str(self.extra))
            )

        super().save(*args, **kwargs)  # First save to get PK

        # Calculate returned amount
        self._returned_amount = self.calculate_returned_amount()
        
        # Check if ANY items were returned
        has_returns = any(item.returned_quantity > 0 for item in self.items.all())
        
        # DEFAULT CASE: No returns - normal calculation
        if not has_returns:
            self._net_amount = max(self.final_amount - self._returned_amount, Decimal('0.00'))
        # RETURN CASE: Add back ALL discounts
        else:
            self._net_amount = max(
                self.final_amount - self._returned_amount + 
                self.discount_amount + self.price_deducted,
                Decimal('0.00')
            )

        self._total_profit = self.calculate_total_profit()
        super().save(update_fields=['_returned_amount', '_net_amount', '_total_profit'])
    
    @property
    def total_discount(self):
        """Returns the sum of discount_amount and price_deducted"""
        return (Decimal(str(self.discount_amount)) + 
                Decimal(str(self.price_deducted))).quantize(Decimal('0.00'))
    
    @property
    def is_fully_returned(self):
        """Check if the sale has been fully returned"""
        return Decimal(str(self.final_amount)) <= Decimal(str(self.returned_amount))

    def calculate_returned_amount(self):
        """Calculate returned amount efficiently"""
        if hasattr(self, '_prefetched_return_items'):
            # Use prefetched data if available
            return sum(
                Decimal(str(item.returned_price))
                for return_entry in getattr(self, '_prefetched_returns', [])
                for item in getattr(return_entry, '_prefetched_items', [])
            )
        else:
            # Fall back to database query
            return self.returns.aggregate(
                total=Sum('items__returned_price')
            )['total'] or Decimal('0.00')

    def calculate_total_profit(self):
        """Profit calculation where ALL discounts are added back if any item returned"""
        if hasattr(self, '_prefetched_items'):
            items = self._prefetched_items
        else:
            items = self.items.all()

        # Check if ANY items were returned
        has_returns = any(item.returned_quantity > 0 for item in items)

        # Calculate base profit
        total_profit = Decimal('0.00')
        for item in items:
            unit_profit = item.selling_price_per_unit - item.purchase_price_per_unit
            net_quantity = item.quantity - item.returned_quantity
            total_profit += unit_profit * net_quantity
            total_profit -= item.discount_per_unit * item.quantity  # Item-level discounts

        # Add extra amount
        total_profit += self.extra

        # DEFAULT CASE: Subtract all discounts
        if not has_returns:
            total_profit -= (self.discount_amount + self.price_deducted)
        # RETURN CASE: Add back ALL discounts (effectively not subtracting them)
        else:
            pass  # Don't subtract any sale-level discounts

        return max(total_profit, Decimal('0.00'))

    @property
    def net_amount(self):
        """Use cached value if available"""
        if hasattr(self, '_net_amount'):
            return self._net_amount
        return self.calculate_net_amount()

    @property
    def total_profit(self):
        """Use cached value if available"""
        if hasattr(self, '_total_profit'):
            return self._total_profit
        return self.calculate_total_profit()

    @property
    def returned_amount(self):
        """Use cached value if available"""
        if hasattr(self, '_returned_amount'):
            return self._returned_amount
        return self.calculate_returned_amount()

    # Class methods for aggregated data
    @classmethod
    def get_sales_data(cls, time_period=None):
        """Get sales data for a specific time period"""
        queryset = cls.objects.all()
        
        if time_period:
            today = timezone.now().date()
            if time_period == 'today':
                queryset = queryset.filter(sale_date__date=today)
            elif time_period == 'weekly':
                last_monday = today - timedelta(days=today.weekday())
                queryset = queryset.filter(sale_date__date__gte=last_monday)
            elif time_period == 'monthly':
                first_of_month = today.replace(day=1)
                queryset = queryset.filter(sale_date__date__gte=first_of_month)
            elif time_period == 'six_months':
                if today.month <= 6:
                    six_month_reset = date(today.year, 1, 1)
                else:
                    six_month_reset = date(today.year, 7, 1)
                queryset = queryset.filter(sale_date__date__gte=six_month_reset)
        
        # Prefetch related data efficiently
        queryset = queryset.prefetch_related(
            'items',
            'returns__items'
        ).order_by('-sale_date')
        
        return queryset

    @classmethod
    def get_aggregated_data(cls, time_period=None):
        """Get aggregated data for dashboard with minimal queries"""
        queryset = cls.get_sales_data(time_period)
        
        # Use annotated aggregates for most calculations
        agg_data = queryset.aggregate(
            total_sales=Count('id'),
            gross_sales=Sum('final_amount'),
            total_net=Sum('_net_amount'),
            total_profit=Sum('_total_profit'),
            total_returned=Sum('_returned_amount')
        )
        
        return {
            'total_sales': agg_data['total_sales'] or 0,
            'gross_sales': agg_data['gross_sales'] or Decimal('0.00'),
            'total_net': agg_data['total_net'] or Decimal('0.00'),
            'total_profit': agg_data['total_profit'] or Decimal('0.00'),
            'total_returned': agg_data['total_returned'] or Decimal('0.00'),
        }
    
    @classmethod
    def total_store_sales_amount(cls):
        return cls.objects.aggregate(
            total=Sum('_net_amount')
        )['total'] or Decimal('0.00')

    @classmethod
    def total_store_profit(cls):
        return cls.objects.aggregate(
            total=Sum('_total_profit')
        )['total'] or Decimal('0.00')

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    medicine = models.ForeignKey('medicine.Medicine', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()

    # Price and cost at time of sale
    selling_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    discount_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        if self.medicine and not self.purchase_price_per_unit:
            self.purchase_price_per_unit = self.medicine.purchase_per_unit_price
        if not self.selling_price_per_unit:
            self.selling_price_per_unit = (
                Decimal(str(self.total_price)) / Decimal(str(self.quantity))
                if self.quantity else Decimal('0.00')
            ).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine.name if self.medicine else 'Deleted Medicine'} x{self.quantity}"

    @property
    def returned_quantity(self):
        """Total quantity returned for this item"""
        result = self.return_items.aggregate(total=Sum('quantity'))['total'] or 0
        return Decimal(str(result))

    @property
    def is_fully_returned(self):
        """Check if this item has been fully returned"""
        return self.returned_quantity >= Decimal(str(self.quantity))

    @property
    def net_quantity(self):
        """Remaining quantity after returns"""
        return Decimal(str(self.quantity)) - Decimal(str(self.returned_quantity))

    @property
    def unit_price(self):
        """Price per unit (after discount)"""
        if self.quantity > 0:
            return (Decimal(str(self.total_price)) / Decimal(str(self.quantity))).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def net_price(self):
        """Total price after returns"""
        return (Decimal(str(self.unit_price)) * Decimal(str(self.net_quantity))).quantize(Decimal('0.01'))

    @property
    def returned_price(self):
        """Total amount returned for this item"""
        return (Decimal(str(self.unit_price)) * Decimal(str(self.returned_quantity))).quantize(Decimal('0.01'))


class Return(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='returns')
    returned_at = models.DateTimeField(auto_now_add=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    reason = models.TextField(blank=True, null=True)

    @property
    def net_quantity(self):
        return self.quantity - self.returned_quantity
    
    @property
    def net_sale_amount(self):
        return self.selling_price_per_unit * self.net_quantity
    
    @property
    def net_profit(self):
        return (self.selling_price_per_unit - self.purchase_price_per_unit) * self.net_quantity
    
    def update_return_calculations(self):
        """Update all return-related calculations"""
        self.returned_price = self.selling_price_per_unit * self.returned_quantity
        self.save()

    def save(self, *args, **kwargs):
        # Calculate refund amount as sum of all return items
        if not self.refund_amount and self.pk:
            self.refund_amount = sum(
                Decimal(str(item.returned_price))
                for item in self.items.all()
            )
        super().save(*args, **kwargs)


class ReturnItem(models.Model):
    return_entry = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='items')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name='return_items')
    quantity = models.PositiveIntegerField()
    returned_price = models.DecimalField(max_digits=10, decimal_places=0)
    restocked = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Calculate returned price based on unit price (after discounts)
        if not self.returned_price:
            self.returned_price = Decimal(str(self.sale_item.unit_price)) * Decimal(str(self.quantity))
        super().save(*args, **kwargs)