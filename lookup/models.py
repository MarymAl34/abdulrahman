# lookup/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.conf import settings

# ------------------------------
# Validators
# ------------------------------
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


# ------------------------------
# مصدر البيانات (بعد استيراد الإكسل)
# ------------------------------
class Customer(models.Model):
    full_name   = models.CharField(_("الاسم"), max_length=255, blank=True)
    meter_no    = models.CharField(_("رقم العداد"), max_length=50, blank=True, db_index=True)
    account_no  = models.CharField(_("رقم الحساب"), max_length=50, blank=True, db_index=True)
    national_id = models.CharField(
        _("رقم الهوية"),
        max_length=10, blank=True, db_index=True,
        validators=[ksa_id_validator]
    )
    mobile      = models.CharField(
        _("رقم الجوال"),
        max_length=15, blank=True, db_index=True,
        validators=[phone_validator]
    )
    unit_code   = models.CharField(_("كود الوحدة"), max_length=50, blank=True, db_index=True)
    email       = models.EmailField(_("البريد الإلكتروني"), blank=True)

    class Meta:
        verbose_name = _("عميل")
        verbose_name_plural = _("العملاء")
        ordering = ["full_name", "account_no"]
        indexes = [
            models.Index(fields=["meter_no"]),
            models.Index(fields=["account_no"]),
            models.Index(fields=["national_id"]),
            models.Index(fields=["mobile"]),
            models.Index(fields=["unit_code"]),
        ]
        # لا نفرض فريدًا لتجنّب مشاكل التكرار الوارد من الإكسل

    def __str__(self):
        return self.full_name or self.account_no or self.national_id or _("عميل")


# ------------------------------
# سجل الاستعلامات/التحديثات
# ------------------------------
class LookupHistory(models.Model):
    class QueryType(models.TextChoices):
        METER = "meter", _("رقم العداد")
        ACCOUNT = "account", _("رقم الحساب")
        NATIONAL = "national", _("رقم الهوية")
        PHONE = "phone", _("رقم الجوال")
        UNIT = "unit", _("كود الوحدة")
        EMAIL = "email", _("البريد الإلكتروني")
        NAME = "name", _("الاسم")
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

    # لقطة من الحقول المُرسلة (اختياري)
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
        v = (self.query_value or "").strip()
        if self.query_type in {self.QueryType.PHONE, self.QueryType.NATIONAL} and len(v) >= 6:
            return f"{v[:3]}***{v[-3:]}"
        elif len(v) > 4:
            return "*" * (len(v) - 4) + v[-4:]
        return v

    # تنظيف بسيط قبل الحفظ
    def clean(self):
        # تطبيع مسافات
        if self.query_value:
            self.query_value = str(self.query_value).strip()

    # مُساعِد لتسجيل السجل من أي فيو بسهولة
    @classmethod
    def log_lookup(
        cls,
        *,
        user=None,
        query_type: str,
        query_value: str,
        form_snapshot: dict | None = None,
        result_found: bool = False,
        action: str = "استعلام",
        message: str = "",
        ip_address: str | None = None,
        user_agent: str = "",
    ):
        data = {
            "user": user,
            "query_type": query_type or cls.QueryType.UNKNOWN,
            "query_value": (query_value or "").strip(),
            "result_found": result_found,
            "action": action or "",
            "message": message or "",
            "ip_address": ip_address,
            "user_agent": user_agent or "",
        }
        # لقطة من الحقول إن توفرت
        form_snapshot = form_snapshot or {}
        data.update({
            "full_name": form_snapshot.get("full_name", "")[:120],
            "meter_number": form_snapshot.get("meter_no") or form_snapshot.get("meter_number", ""),
            "account_number": form_snapshot.get("account_no") or form_snapshot.get("account_number", ""),
            "national_id": form_snapshot.get("national_id", ""),
            "phone": form_snapshot.get("mobile") or form_snapshot.get("phone", ""),
            "unit_code": form_snapshot.get("unit_code", ""),
            "email": form_snapshot.get("email", ""),
        })
        return cls.objects.create(**data)
