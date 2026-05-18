from django.urls import path
from . import views

urlpatterns = [
    path('', views.predict_traffic, name='predict_traffic'),
    path('chatbot/predict/', views.chatbot_predict, name='chatbot_predict'),
]
