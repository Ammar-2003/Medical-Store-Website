from django.urls import path
from .views import (
    MedicineInventoryView, 
    MedicineUpdateView, MedicineDeleteView , MedicineDetailView , MedicineDashboardView
)
from .views import medicine_suggestions , search_purchases


urlpatterns = [
    path('', MedicineInventoryView.as_view(), name='medicine'),
    path('edit/<int:pk>/', MedicineUpdateView.as_view(), name='update_medecine'),
    path('delete/<int:pk>/', MedicineDeleteView.as_view(), name='delete_medicine'),
    path('suggestions/', medicine_suggestions, name='medicine_suggestions'),
    path('detail/<int:pk>/', MedicineDetailView.as_view(), name='medicine_detail'),
    path('medicine-dashboard/', MedicineDashboardView.as_view(), name='medicine_dashboard'),
    path('search-purchases/', search_purchases, name='search_purchases'),
]