from django.urls import path
from . import views

urlpatterns = [
    path('', views.predict_traffic, name='predict_traffic'),
    path('chatbot/predict/', views.chatbot_predict, name='chatbot_predict'),
    path('sms/africastalking/', views.africastalking_sms_webhook, name='africastalking_sms_webhook'),
    path('subscribe/', views.subscribe, name='subscribe'),
]
