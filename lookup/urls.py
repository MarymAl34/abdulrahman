# lookup/urls.py
from django.urls import path
from . import views

app_name = "lookup"

urlpatterns = [
    # الصفحة الرئيسية للاستعلام عن البيانات
    path("", views.data_lookup_view, name="home"),

    # سجل الاستدعاءات
    path("history/", views.lookup_history_view, name="history"),

    # اختيار الدور (مستفيد/مالك)
    path("choose-role/", views.choose_role_view, name="choose_role"),

    # صفحة الخدمات (موحدة للجميع + شارة الدور)
    path("services/", views.services_view, name="services"),

    # إنشاء/استعراض طلب لخدمة معيّنة (يُستخدم داخل services.html)
    path("services/<slug:key>/", views.service_request_view, name="service_request"),
]
