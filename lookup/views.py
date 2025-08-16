# lookup/views.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Iterable, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from .models import LookupHistory  # <= التسجيل في السجل

# نحاول استيراد pandas/openpyxl لقراءة Excel، وإن لم تتوفر نستمر بدون بحث فعلي
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:  # pragma: no cover
    HAS_PANDAS = False


# ===================== إعدادات عامة =====================
MAX_PREVIEW_ROWS = 100                     # عدد صفوف المعاينة
DATA_DIR = Path(settings.BASE_DIR) / "data_files"  # مجلد ملفات الإكسل


# ===================== أدوات مساعدة =====================
def _digits(s: Optional[str]) -> str:
    """إرجاع الأرقام فقط من النص (مع التعامل مع None)."""
    return "".join(ch for ch in (s or "").strip() if ch.isdigit())


def _to_str(v) -> str:
    """
    تحويل القيم لنص بسيط. إذا كانت قيمة رقمية 12.0 مثلاً نحولها إلى '12'
    لتفادي تباينات Excel.
    """
    if v is None:
        return ""
    try:
        f = float(v)
        if f.is_integer():
            return str(int(f))
        return str(v).strip()
    except Exception:
        return str(v).strip()


def _normalize_series_to_str(series):
    """تطبيع Series إلى نصوص بسيطة للمقارنة."""
    return series.map(_to_str)


def _norm(s: str) -> str:
    """تطبيع نصي للأسماء (إزالة مسافات جانبية + خفض حالة)."""
    return (s or "").strip().casefold()


def _latest_excel_file() -> Optional[Path]:
    """إرجاع أحدث ملف .xlsx داخل data_files إن وجد."""
    if not DATA_DIR.exists():
        return None
    files = sorted(DATA_DIR.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _by_candidates(df_cols: Iterable[str], candidates: Iterable[str]) -> List[str]:
    """
    إرجاع الأعمدة الموجودة فعليًا في DataFrame من ضمن قائمة مرشحين (مع تطبيع الاسم).
    يدعم فروق المسافات/الحالة (عربي/إنجليزي).
    """
    df_map = {_norm(c): c for c in df_cols}
    picked: List[str] = []
    for c in candidates:
        key = _norm(c)
        if key in df_map:
            picked.append(df_map[key])
    return picked


# خرائط أسماء الأعمدة المحتملة (عربي/إنجليزي)
CANDIDATES: Dict[str, List[str]] = {
    "meter_number":   ["رقم العداد", "Meter", "Meter No", "MeterNo", "MeterNumber"],
    "account_number": ["رقم الحساب", "Account", "Account No", "AccountNo", "AccountNumber"],
    "national_id":    ["رقم الهوية", "هوية", "National ID", "NationalId", "ID"],
    "phone":          ["رقم الجوال", "جوال", "Mobile", "Phone", "PhoneNumber", "MobileNumber"],
    "unit_code":      ["كود الوحدة", "Unit", "Unit Code", "UnitCode"],
    "email":          ["الايميل", "البريد", "Email", "E-mail"],
}


def _detect_query_type(data: Dict[str, str]) -> str:
    """تحديد نوع المعرف المستخدم بناءً على أول حقل مُعبأ."""
    if data.get("meter_number"):
        return LookupHistory.QueryType.METER
    if data.get("account_number"):
        return LookupHistory.QueryType.ACCOUNT
    if data.get("national_id"):
        return LookupHistory.QueryType.NATIONAL
    if data.get("phone"):
        return LookupHistory.QueryType.PHONE
    if data.get("unit_code"):
        return LookupHistory.QueryType.UNIT
    return LookupHistory.QueryType.UNKNOWN


# ===================== الواجهة الرئيسية =====================
@login_required(login_url=reverse_lazy("access:login"))
def data_lookup_view(request):
    """
    صفحة استدعاء البيانات:
    - تجمع المُدخلات وتتحقق منها بشكل خفيف.
    - اختياريًا: تبحث داخل أحدث ملف Excel في data_files.
    - تعرض معاينة حتى MAX_PREVIEW_ROWS، وتُسجّل العملية في LookupHistory.
    """
    # قيم مبدئية (نملأ الجوال من اسم المستخدم إن كان رقمًا)
    initial = {
        "full_name": "",
        "meter_number": "",
        "account_number": "",
        "national_id": "",
        "phone": _digits(getattr(request.user, "username", "")) or "",
        "unit_code": "",
        "email": "",
    }

    if request.method == "POST":
        data = {
            "full_name":     (request.POST.get("full_name") or "").strip(),
            "meter_number":  (request.POST.get("meter_number") or "").strip(),
            "account_number": (request.POST.get("account_number") or "").strip(),
            "national_id":   _digits(request.POST.get("national_id")),
            "phone":         _digits(request.POST.get("phone")),
            "unit_code":     (request.POST.get("unit_code") or "").strip(),
            "email":         (request.POST.get("email") or "").strip(),
        }
        action = (request.POST.get("action") or "lookup").strip()  # في حال استخدمت أزرار متعددة

        errors: Dict[str, str] = {}

        # يلزم تعبئة حقل واحد على الأقل من مُعرّفات البحث
        if not any([data["meter_number"], data["account_number"], data["national_id"], data["phone"], data["unit_code"]]):
            errors["__all__"] = _("فضلاً عبّئ حقلًا واحدًا على الأقل من حقول الاستعلام.")

        # تحققات خفيفة
        if data["national_id"] and len(data["national_id"]) != 10:
            errors["national_id"] = _("رقم الهوية يجب أن يكون 10 أرقام.")

        if data["phone"] and not (9 <= len(data["phone"]) <= 15):
            errors["phone"] = _("رقم الجوال غير صالح (9–15 رقم).")

        for key in ("meter_number", "account_number", "unit_code"):
            if data[key] and len(data[key]) < 3:
                errors[key] = _("القيمة قصيرة جدًا.")

        if data["email"]:
            try:
                validate_email(data["email"])
            except ValidationError:
                errors["email"] = _("البريد الإلكتروني غير صالح.")

        # لو في أخطاء، نعرضها وننهي
        if errors:
            for msg in errors.values():
                if msg:
                    messages.error(request, msg)
            # نسجل العملية مع كونها فاشلة (بدون بحث)
            _log_lookup(request, data, result_found=False, action=action, message=_("فشل التحقق من المدخلات."))
            return render(request, "lookup/data_lookup.html", {"data": {**initial, **data}, "errors": errors})

        # ======== البحث في ملف Excel (إن توفرت المتطلبات) ========
        results: List[Dict] = []
        columns: List[str] = []
        source_file: Optional[str] = None
        count_total = 0
        count_shown = 0

        if HAS_PANDAS:
            xlsx = _latest_excel_file()
            if xlsx and xlsx.exists():
                source_file = xlsx.name
                try:
                    df = pd.read_excel(xlsx, engine="openpyxl")
                    df.columns = [str(c).strip() for c in df.columns]

                    mask = pd.Series(True, index=df.index)

                    for key, value in data.items():
                        if key in ("full_name", "email"):  # هذان الحقلان لا نستخدمهما كمعرفات للبحث
                            continue
                        if not value:
                            continue

                        cols = _by_candidates(df.columns, CANDIDATES.get(key, []))
                        if not cols:
                            continue

                        sub_any = pd.Series(False, index=df.index)
                        for c in cols:
                            series = _normalize_series_to_str(df[c])
                            cmp_value = value
                            if key in ("phone", "national_id"):
                                series = series.map(_digits)
                                cmp_value = _digits(value)
                            sub_any |= (series == cmp_value)

                        mask &= sub_any

                    filtered = df[mask].copy()
                    count_total = int(filtered.shape[0])

                    preview = filtered.head(MAX_PREVIEW_ROWS).fillna("")
                    count_shown = int(preview.shape[0])
                    columns = list(preview.columns)
                    results = preview.to_dict(orient="records")

                    if count_total == 0:
                        messages.warning(request, _("لم يتم العثور على نتائج مطابقة."))
                    else:
                        messages.success(
                            request,
                            _("تم العثور على %(n)d نتيجة (المعروض %(m)d).") % {"n": count_total, "m": count_shown}
                        )
                except Exception as e:
                    messages.error(request, _("تعذّر قراءة ملف الإكسل: ") + str(e))
            else:
                messages.info(request, _("لا يوجد ملف Excel داخل المجلد data_files."))
        else:
            messages.info(request, _("لتفعيل البحث من ملف الإكسل، ثبّت pandas و openpyxl ثم أعد المحاولة."))

        # نسجل العملية في السجل
        _log_lookup(
            request,
            data,
            result_found=(count_total > 0),
            action=action,
            message=_("ملف المصدر: %(f)s") % {"f": (source_file or _("غير متوفر"))},
        )

        return render(
            request,
            "lookup/data_lookup.html",
            {
                "data": {**initial, **data},
                "errors": {},
                "results": results,
                "columns": columns,
                "source_file": source_file,
                "count_total": count_total,
                "count_shown": count_shown,
            },
        )

    # ======== GET ========
    return render(request, "lookup/data_lookup.html", {"data": initial, "errors": {}})


# ===================== تسجيل السجل =====================
def _log_lookup(request, data: Dict[str, str], *, result_found: bool, action: str, message: str = "") -> None:
    """حفظ سجل العملية في LookupHistory مع لقطة من المدخلات."""
    try:
        LookupHistory.objects.create(
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            query_type=_detect_query_type(data),
            query_value=(
                data.get("meter_number")
                or data.get("account_number")
                or data.get("national_id")
                or data.get("phone")
                or data.get("unit_code")
                or ""
            ),
            full_name=data.get("full_name", ""),
            meter_number=data.get("meter_number", ""),
            account_number=data.get("account_number", ""),
            national_id=data.get("national_id", ""),
            phone=data.get("phone", ""),
            unit_code=data.get("unit_code", ""),
            email=data.get("email", ""),
            action=action,
            result_found=result_found,
            message=message[:255] if message else "",
            ip_address=(request.META.get("REMOTE_ADDR") or None),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )
    except Exception:
        # ما نكسر الصفحة لو فشل السجل
        pass
# === عرض سجل الاستدعاءات مع ترشيحات بسيطة ===
from django.core.paginator import Paginator
from django.db.models import Q
from .models import LookupHistory

@login_required(login_url=reverse_lazy("access:login"))
def lookup_history_view(request):
    qs = LookupHistory.objects.all()

    # فلاتر اختيارية عبر معلمات GET
    q = (request.GET.get("q") or "").strip()
    t = (request.GET.get("type") or "").strip()      # meter/account/national/phone/unit/unknown
    r = request.GET.get("found")                     # "1" أو "0"

    if q:
        qs = qs.filter(
            Q(query_value__icontains=q) |
            Q(full_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(national_id__icontains=q) |
            Q(account_number__icontains=q) |
            Q(meter_number__icontains=q) |
            Q(unit_code__icontains=q) |
            Q(email__icontains=q)
        )
    if t:
        qs = qs.filter(query_type=t)
    if r in ("0", "1"):
        qs = qs.filter(result_found=(r == "1"))

    paginator = Paginator(qs, 20)  # 20 سجل في الصفحة
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "lookup/history.html", {
        "page_obj": page_obj,
        "types": LookupHistory.QueryType.choices,
        "q": q, "t": t, "r": r,
    })
