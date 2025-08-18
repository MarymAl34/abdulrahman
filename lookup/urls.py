# lookup/urls.py
from django.urls import path
from . import views

app_name = 'lookup'

urlpatterns = [
    # الصفحة الرئيسية للاستعلام عن البيانات
    path('', views.data_lookup_view, name='home'),

    # صفحة عرض سجل الاستدعاءات
    path('history/', views.lookup_history_view, name='history'),

    # صفحة اختيار الدور (مستفيد أو مالك)
    path('role/', views.role_select_view, name='role_select'),

    # صفحة الخدمات (حسب الدور المختار)
    path('services/', views.services_page_view, name='services_page'),
]
