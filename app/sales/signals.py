# sales/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import SaleItem, ReturnItem

@receiver([post_save, post_delete], sender=SaleItem)
def update_sale_profit_on_item_change(sender, instance, **kwargs):
    """Update sale profit whenever sale items change"""
    instance.sale._total_profit = instance.sale.calculate_total_profit()
    instance.sale.save(update_fields=['_total_profit'])

@receiver([post_save, post_delete], sender=ReturnItem)
def update_sale_profit_on_return_change(sender, instance, **kwargs):
    """Update sale profit whenever return items change"""
    instance.return_entry.sale._total_profit = instance.return_entry.sale.calculate_total_profit()
    instance.return_entry.sale.save(update_fields=['_total_profit'])