from django.urls import path
from django.views.generic import TemplateView

app_name = 'lookup'

urlpatterns = [
    # صفحة رئيسية تجريبية لتطبيق lookup
    path('', TemplateView.as_view(template_name='lookup/lookup_home.html'), name='home'),
]
