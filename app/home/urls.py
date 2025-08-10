# your_app/urls.py
from django.urls import path
from .views import HomeView , search_by_formula , medicine_search_results

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('search-by-formula/', search_by_formula, name='search_by_formula'),
    path('suggestions/', medicine_search_results, name='medicine_search_results'),


]
