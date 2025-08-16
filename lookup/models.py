from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.conf import settings

# مدققات بسيطة (اختيارية)
ksa_id_validator = RegexValidator(
    r"^\d{10}$",
    _("رقم الهوية يجب أن يكون 10 أرقام."),
    code="invalid_nid"
)
phone_validator = RegexValidator(
    r"^\d{9,15}$",
    _("رقم الجوال غير صالح (9–15 رقم)."),
    code="invalid_phone"
)


class LookupHistory(models.Model):
    class QueryType(models.TextChoices):
        METER = "meter", _("رقم العداد")
        ACCOUNT = "account", _("رقم الحساب")
        NATIONAL = "national", _("رقم الهوية")
        PHONE = "phone", _("رقم الجوال")
        UNIT = "unit", _("كود الوحدة")
        UNKNOWN = "unknown", _("غير محدد")

    # مَن نفّذ العملية (اختياري)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name=_("المستخدم"),
        related_name="lookup_histories",
    )

    # ما الذي بُحث به؟
    query_type = models.CharField(
        _("نوع المعرّف"),
        max_length=50,
        choices=QueryType.choices,
        default=QueryType.UNKNOWN
    )
    query_value = models.CharField(
        _("القيمة المُستخدمة في البحث"),
        max_length=100
    )

    # لقطة من الحقول المُرسلة في النموذج (اختيارية)
    full_name = models.CharField(_("الاسم"), max_length=120, blank=True)
    meter_number = models.CharField(_("رقم العداد"), max_length=50, blank=True)
    account_number = models.CharField(_("رقم الحساب"), max_length=50, blank=True)
    national_id = models.CharField(
        _("رقم الهوية"),
        max_length=10,
        blank=True,
        validators=[ksa_id_validator]
    )
    phone = models.CharField(
        _("رقم الجوال"),
        max_length=15,
        blank=True,
        validators=[phone_validator]
    )
    unit_code = models.CharField(_("كود الوحدة"), max_length=50, blank=True)
    email = models.EmailField(_("البريد الإلكتروني"), blank=True)

    # نتيجة العملية
    action = models.CharField(
        _("نوع العملية"),
        max_length=20,
        blank=True,
        help_text=_("مثل: استعلام / تحديث")
    )
    result_found = models.BooleanField(_("تم العثور على النتيجة"), default=False)
    message = models.CharField(_("ملاحظة/رسالة النظام"), max_length=255, blank=True)

    # تتبع
    ip_address = models.GenericIPAddressField(_("عنوان IP"), blank=True, null=True)
    user_agent = models.CharField(_("المتصفح/العميل"), max_length=255, blank=True)
    timestamp = models.DateTimeField(_("وقت العملية"), auto_now_add=True)

    class Meta:
        verbose_name = _("سجل استدعاء بيانات")
        verbose_name_plural = _("سجلات استدعاء البيانات")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["query_type", "query_value"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(query_value=""),
                name="lookup_query_value_not_empty"
            ),
        ]

    def __str__(self) -> str:
        qt = self.get_query_type_display() or _("غير محدد")
        status = _("تم العثور") if self.result_found else _("لم يتم العثور")
        return f"{qt}: {self.query_value} — {status}"

    @property
    def masked_value(self) -> str:
        """إخفاء جزء من القيم الحساسة عند العرض."""
        v = self.query_value or ""
        if self.query_type in {self.QueryType.PHONE, self.QueryType.NATIONAL} and len(v) >= 6:
            return f"{v[:3]}***{v[-3:]}"
        elif len(v) > 4:
            return "*" * (len(v) - 4) + v[-4:]
        return v
