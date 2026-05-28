from django.urls import path
from . import views

urlpatterns = [
    path('', views.predict_traffic, name='predict_traffic'),
    path('subscribe/', views.subscribe, name='subscribe'),
]