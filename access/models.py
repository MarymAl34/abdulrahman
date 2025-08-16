from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class AccessLog(models.Model):
    class Actions(models.TextChoices):
        LOGIN  = "LOGIN",  _("تسجيل دخول")
        LOGOUT = "LOGOUT", _("تسجيل خروج")
        OTP    = "OTP",    _("تحقق OTP")
        VIEW   = "VIEW",   _("عرض صفحة")
        FAIL   = "FAIL",   _("محاولة فاشلة")

    user_identifier = models.CharField(
        _("معرّف المستخدم"),
        max_length=100,
        help_text=_("مثال: رقم الجوال أو البريد الإلكتروني"),
        db_index=True,
    )
    action = models.CharField(
        _("الإجراء"),
        max_length=20,
        choices=Actions.choices,
        default=Actions.VIEW,
        db_index=True,
    )
    timestamp = models.DateTimeField(
        _("وقت التنفيذ"),
        auto_now_add=True,
        db_index=True,
    )
    ip_address = models.GenericIPAddressField(
        _("عنوان IP"),
        null=True,
        blank=True,
        help_text=_("يُسجل عند توفره"),
    )
    user_agent = models.CharField(
        _("متصفح/عميل"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_("سلاسل واصف المتصفح عند الحاجة"),
    )

    class Meta:
        verbose_name = _("سجل دخول")
        verbose_name_plural = _("سجلات الدخول")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user_identifier", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "—"
        return f"{self.user_identifier} • {self.get_action_display()} • {ts}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("المستخدم"),
    )
    phone = models.CharField(_("رقم الجوال"), max_length=15, unique=True)
    national_id = models.CharField(_("رقم الهوية"), max_length=20)

    class Meta:
        verbose_name = _("ملف مستخدم")
        verbose_name_plural = _("ملفات المستخدمين")

    def __str__(self):
        return f"{self.user.username} ({self.phone})"

# access/models.py (أضيفي في آخر الملف)
from django.utils import timezone
import random
import string

class OTPRequest(models.Model):
    phone = models.CharField("رقم الجوال", max_length=15, db_index=True)
    code = models.CharField("رمز التحقق", max_length=6)
    created_at = models.DateTimeField("وقت الإرسال", default=timezone.now)
    attempts = models.PositiveSmallIntegerField("عدد المحاولات", default=0)

    class Meta:
        verbose_name = "رمز تحقق"
        verbose_name_plural = "رموز التحقق"
        indexes = [models.Index(fields=["phone", "created_at"])]

    def is_valid(self, window_minutes: int = 5) -> bool:
        """صالح لمدة 5 دقائق افتراضيًا"""
        return timezone.now() - self.created_at <= timezone.timedelta(minutes=window_minutes)

    @staticmethod
    def generate_code() -> str:
        # 6 أرقام
        return "".join(random.choices(string.digits, k=6))

    def __str__(self):
        return f"{self.phone} - {self.code} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
