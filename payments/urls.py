from django.urls import path

from payments.views import MomoWebhookView

urlpatterns = [
    path('payments/webhook/momo/', MomoWebhookView.as_view(), name='momo-webhook'),
]
