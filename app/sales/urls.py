from django.urls import path
from .views import (
    CartView, CheckoutView, ReceiptView,
    SalesDashboardView, SaleDetailView, SalesListView , ReportListView , CreateReturnView , ReturnView , delete_sale
)
app_name = 'sales'
urlpatterns = [
    path('', SalesDashboardView.as_view(), name='dashboard'),
    path('cart/', CartView.as_view(), name='cart'),
    path('cart/update/', CartView.as_view(), name='update_cart'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('receipt/<int:pk>/', ReceiptView.as_view(), name='receipt'),
    path('list/', SalesListView.as_view(), name='list'),
    path('report/', ReportListView.as_view(), name='report'),
    path('detail/<int:pk>/', SaleDetailView.as_view(), name='detail'),
    path('<int:sale_id>/return/', CreateReturnView.as_view(), name='create_return'),
    path('return/', ReturnView.as_view(), name='return'),
    path('delete-sale/<int:pk>/', delete_sale, name='delete'),

]