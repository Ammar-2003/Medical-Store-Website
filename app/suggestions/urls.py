from django.urls import path
from .views import analyze_symptoms

urlpatterns = [
    path("analyze-symptoms/", analyze_symptoms, name="analyze_symptoms"),
]