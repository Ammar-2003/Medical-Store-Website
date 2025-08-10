from django.contrib import admin
from .models import Sale , SaleItem , Return , ReturnItem
# Register your models here.

admin.site.register(Sale)
admin.site.register(SaleItem)
admin.site.register(Return)
admin.site.register(ReturnItem)