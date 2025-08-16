# access/urls.py
from django.urls import path
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

from .views import signup_view, verify_otp_view, login_view, logout_view

app_name = "access"

urlpatterns = [
    # دخول مباشر على /access/ يحوّل لصفحة التسجيل
    path("", RedirectView.as_view(pattern_name="access:signup", permanent=False)),

    # مصادقة أساسية
    path("signup/", signup_view, name="signup"),
    path("verify-otp/", verify_otp_view, name="verify_otp"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # ===== إعادة تعيين كلمة المرور (Password Reset) =====
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="access/password_reset_form.html",
            email_template_name="access/password_reset_email.txt",
            subject_template_name="access/password_reset_subject.txt",
            success_url="/access/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="access/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="access/password_reset_confirm.html",
            success_url="/access/reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="access/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
