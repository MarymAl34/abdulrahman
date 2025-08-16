# lookup/urls.py
from django.urls import path
from . import views

app_name = 'lookup'

urlpatterns = [
    # الصفحة الرئيسية للاستعلام عن البيانات
    path('', views.data_lookup_view, name='home'),

    # صفحة عرض سجل الاستدعاءات
    path('history/', views.lookup_history_view, name='history'),
]
