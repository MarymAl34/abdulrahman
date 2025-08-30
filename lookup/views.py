# lookup/views.py
from __future__ import annotations

from typing import Dict, Optional, List, TypedDict
from types import SimpleNamespace
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Customer, LookupHistory


# ===================== أدوات مساعدة =====================

def _digits(s: Optional[str]) -> str:
    """إرجاع الأرقام فقط (يتحمل None)."""
    return "".join(ch for ch in (s or "").strip() if ch.isdigit())


def _detect_query_type(data: Dict[str, str]) -> str:
    """تحديد نوع المعرف المستخدم بناءً على أول حقل مُعبأ."""
    if data.get("meter_number"):   return LookupHistory.QueryType.METER
    if data.get("account_number"): return LookupHistory.QueryType.ACCOUNT
    if data.get("national_id"):    return LookupHistory.QueryType.NATIONAL
    if data.get("phone"):          return LookupHistory.QueryType.PHONE
    if data.get("unit_code"):      return LookupHistory.QueryType.UNIT
    if data.get("email"):          return LookupHistory.QueryType.EMAIL
    if data.get("full_name"):      return LookupHistory.QueryType.NAME
    return LookupHistory.QueryType.UNKNOWN


def _log_lookup(request, data: Dict[str, str], *, result_found: bool, action: str, message: str = "") -> None:
    """حفظ سجل العملية في LookupHistory مع لقطة من المدخلات."""
    try:
        LookupHistory.objects.create(
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            query_type=_detect_query_type(data),
            query_value=(
                data.get("meter_number") or data.get("account_number") or data.get("national_id")
                or data.get("phone") or data.get("unit_code") or data.get("email")
                or data.get("full_name") or ""
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
            message=(message or "")[:255],
            ip_address=(request.META.get("REMOTE_ADDR") or None),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )
    except Exception:
        # لا نكسر الصفحة إذا فشل التسجيل في السجل
        pass


def _simple_customer_from_dict(d: Dict[str, str]) -> SimpleNamespace:
    """إنشاء كائن بسيط يماثل Customer عند الإدخال اليدوي."""
    return SimpleNamespace(
        id=None,
        full_name=d.get("full_name") or "",
        meter_no=d.get("meter_number") or "",
        account_no=d.get("account_number") or "",
        national_id=d.get("national_id") or "",
        mobile=d.get("phone") or "",
        unit_code=d.get("unit_code") or "",
        email=d.get("email") or "",
    )


def _has_minimum_manual_info(d: Dict[str, str]) -> bool:
    """
    مسموح نكمل يدويًا لو:
    - الاسم موجود، و
    - أي معرف واقعي (هوية 10 أرقام، أو جوال، أو رقم عداد/حساب/كود وحدة).
    """
    if not d.get("full_name"):
        return False
    if d.get("national_id") and len(d["national_id"]) == 10:
        return True
    if d.get("phone"):
        return True
    if d.get("meter_number") or d.get("account_number") or d.get("unit_code"):
        return True
    return False


class ServiceItem(TypedDict):
    key: str
    title: str
    desc: str
    href: str


def _services_catalog() -> List[ServiceItem]:
    """
    الكتالوج الموحد للخدمات (نفسه للمستفيد والمالك).
    """
    return [
        {"key": "transfer_meter",     "title": _("طلب نقل عداد"),                         "desc": _("نقل عداد الكهرباء/المياه."),                         "href": "#"},
        {"key": "pay_debt",           "title": _("طلب تسديد مديونية"),                   "desc": _("سداد المديونيات بشكل آمن."),                         "href": "#"},
        {"key": "manual_request",     "title": _("طلب يدوي (نقل ملكية – تصحيح بيانات – طلب دعم…)"), "desc": _("طلبات متنوعة تُستلم يدويًا."),      "href": "#"},
        {"key": "account_verify",     "title": _("طلب توثيق الحساب"),                    "desc": _("توثيق وربط الحساب بالمستخدم."),                       "href": "#"},
        {"key": "activate_service",   "title": _("طلب تفعيل الخدمة"),                    "desc": _("تفعيل خدمة الكهرباء/المياه."),                        "href": "#"},
        {"key": "beneficiary_update", "title": _("تحديث بيانات المستفيد"),               "desc": _("تعديل بيانات التواصل."),                              "href": "#"},
        {"key": "manual_ticket",      "title": _("بلاغ أو استفسار يدوي"),                 "desc": _("إنشاء بلاغ/استفسار ومتابعته."),                      "href": "#"},
    ]


def _generate_ref() -> str:
    """توليد رقم مرجعي مختصر، مثال: UW-250820-9F3A7C"""
    return f"UW-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"


def _send_notification(customer_obj, ref: str, service_title: str) -> None:
    """
    إشعارات تجريبية إلى الكونسول (مثل OTP) — استبدليها لاحقًا بإرسال فعلي.
    """
    phone = getattr(customer_obj, "mobile", "") or "-"
    email = getattr(customer_obj, "email", "") or "-"
    print(f"[DEV] SMS to {phone}: تم إنشاء طلب '{service_title}'. رقمك المرجعي: {ref}")
    print(f"[DEV] EMAIL to {email}: تم إنشاء طلب '{service_title}'. رقمك المرجعي: {ref}")


# ===================== استدعاء البيانات =====================

@login_required(login_url=reverse_lazy("access:login"))
def data_lookup_view(request):
    """
    - يقبل إدخال معرف واحد على الأقل.
    - تطابق واحد → الانتقال لاختيار الدور.
    - لا تطابق مع توفر بيانات كافية → إكمال يدوي ثم اختيار الدور.
    - عدة نتائج → إظهار قائمة جزئية.
    """
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
            "full_name": (request.POST.get("full_name") or "").strip(),
            "meter_number": (request.POST.get("meter_number") or "").strip(),
            "account_number": (request.POST.get("account_number") or "").strip(),
            "national_id": _digits(request.POST.get("national_id")),
            "phone": _digits(request.POST.get("phone")),
            "unit_code": (request.POST.get("unit_code") or "").strip(),
            "email": (request.POST.get("email") or "").strip(),
        }
        action = (request.POST.get("action") or "lookup").strip()

        errors: Dict[str, str] = {}
        if not any(data.values()):
            errors["__all__"] = _("فضلاً عبّئ حقلًا واحدًا على الأقل من حقول الاستعلام.")
        if data["national_id"] and len(data["national_id"]) != 10:
            errors["national_id"] = _("رقم الهوية يجب أن يكون 10 أرقام.")
        if data["phone"] and not (9 <= len(data["phone"]) <= 15):
            errors["phone"] = _("رقم الجوال غير صالح.")
        for key in ("meter_number", "account_number", "unit_code"):
            if data[key] and len(data[key]) < 3:
                errors[key] = _("القيمة قصيرة جدًا.")
        if data["email"]:
            try:
                validate_email(data["email"])
            except ValidationError:
                errors["email"] = _("البريد الإلكتروني غير صالح.")

        if errors:
            for msg in errors.values():
                if msg:
                    messages.error(request, msg)
            _log_lookup(request, data, result_found=False, action=action, message=_("فشل التحقق."))
            return render(request, "lookup/data_lookup.html", {"data": {**initial, **data}, "errors": errors})

        # البحث
        q = Q()
        if data["full_name"]:      q &= Q(full_name__icontains=data["full_name"])
        if data["meter_number"]:   q &= Q(meter_no__iexact=data["meter_number"])
        if data["account_number"]: q &= Q(account_no__iexact=data["account_number"])
        if data["national_id"]:    q &= Q(national_id__iexact=data["national_id"])
        if data["phone"]:          q &= Q(mobile__iexact=data["phone"])
        if data["unit_code"]:      q &= Q(unit_code__iexact=data["unit_code"])
        if data["email"]:          q &= Q(email__iexact=data["email"])

        queryset = Customer.objects.filter(q)
        count = queryset.count()

        if count == 0:
            # نكمل يدويًا لو المدخلات كافية
            if _has_minimum_manual_info(data):
                request.session["customer_source"] = "manual"
                request.session["customer_data"] = data
                _log_lookup(request, data, result_found=True, action=action, message=_("إدخال يدوي بلا تطابق."))
                messages.info(request, _("لم نجد تطابقًا في النظام، سنُكمل بالبيانات المدخلة."))
                return redirect("lookup:choose_role")

            messages.warning(request, _("لا نتائج مطابقة."))
            _log_lookup(request, data, result_found=False, action=action, message=_("لا نتائج."))
            return render(request, "lookup/data_lookup.html", {"data": {**initial, **data}, "errors": {}})

        if count == 1:
            selected = queryset.first()
            request.session["customer_source"] = "db"
            request.session["customer_id"] = selected.id
            _log_lookup(request, data, result_found=True, action=action, message=_("تطابق واحد."))
            return redirect("lookup:choose_role")

        # نتائج متعددة
        results_qs = queryset.only("full_name", "account_no", "national_id", "mobile", "unit_code")[:50]
        messages.success(request, _(f"عدد النتائج: {count} (المعروض: {results_qs.count()})"))
        _log_lookup(request, data, result_found=True, action=action, message=_("نتائج متعددة."))
        return render(
            request,
            "lookup/data_lookup.html",
            {"data": {**initial, **data}, "errors": {}, "results": results_qs, "selected": None},
        )

    # GET
    return render(request, "lookup/data_lookup.html", {"data": initial, "errors": {}, "results": None, "selected": None})


# ===================== اختيار الدور =====================

@login_required(login_url=reverse_lazy("access:login"))
def choose_role_view(request):
    source = request.session.get("customer_source")
    customer_obj = None

    if source == "db":
        cid = request.session.get("customer_id")
        if not cid:
            return redirect("lookup:home")
        customer_obj = get_object_or_404(Customer, id=cid)
    elif source == "manual":
        data = request.session.get("customer_data")
        if not data:
            return redirect("lookup:home")
        customer_obj = _simple_customer_from_dict(data)
    else:
        return redirect("lookup:home")

    if request.method == "POST":
        role = request.POST.get("role")
        if role in ("beneficiary", "owner"):
            request.session["role"] = role
            return redirect("lookup:services")
        messages.error(request, _("فضلاً اختر نوع المستخدم."))

    return render(request, "lookup/role_select.html", {"customer": customer_obj})


# ===================== صفحة الخدمات (قالب موحد) =====================

@login_required(login_url=reverse_lazy("access:login"))
def services_view(request):
    """
    صفحة خدمات موحدة للجميع، مع شارة توضح الدور المختار.
    يعتمد على مصدر العميل (قاعدة البيانات أو إدخال يدوي).
    """
    source = request.session.get("customer_source")
    role = request.session.get("role")  # "beneficiary" أو "owner"

    if role not in ("beneficiary", "owner") or source not in ("db", "manual"):
        return redirect("lookup:home")

    if source == "db":
        cid = request.session.get("customer_id")
        if not cid:
            return redirect("lookup:home")
        customer_obj = get_object_or_404(Customer, id=cid)
    else:
        data = request.session.get("customer_data") or {}
        customer_obj = _simple_customer_from_dict(data)

    # بناء الروابط إلى المنظر العام لكل خدمة
    services = _services_catalog()
    for s in services:
        s["href"] = reverse("lookup:service_request", args=[s["key"]])

    return render(
        request,
        "lookup/services.html",
        {
            "customer": customer_obj,
            "role": role,
            "is_beneficiary": role == "beneficiary",
            "services": services,
        },
    )


# ===================== إنشاء الطلب العام =====================

@login_required(login_url=reverse_lazy("access:login"))
def service_request_view(request, key: str):
    """
    منظر عام لكل الخدمات:
    - يتحقق من الجلسة والدور.
    - يولد رقمًا مرجعيًا.
    - يسجّل العملية في LookupHistory.
    - يرسل إشعارًا تجريبيًا (SMS/Email via console).
    - يعيد التوجيه لصفحة الخدمات مع رسالة نجاح.
    """
    source = request.session.get("customer_source")
    role = request.session.get("role")
    if role not in ("beneficiary", "owner") or source not in ("db", "manual"):
        return redirect("lookup:home")

    # جلب بيانات العميل
    if source == "db":
        cid = request.session.get("customer_id")
        if not cid:
            return redirect("lookup:home")
        customer_obj = get_object_or_404(Customer, id=cid)
    else:
        data = request.session.get("customer_data") or {}
        customer_obj = _simple_customer_from_dict(data)

    # تحقق من مفتاح الخدمة
    catalog = {s["key"]: s for s in _services_catalog()}
    svc = catalog.get(key)
    if not svc:
        messages.error(request, _("الخدمة غير متاحة."))
        return redirect("lookup:services")

    # إنشاء مرجع وتسجيل
    ref = _generate_ref()
    _log_lookup(
        request,
        data={
            "full_name": getattr(customer_obj, "full_name", ""),
            "account_number": getattr(customer_obj, "account_no", ""),
            "national_id": getattr(customer_obj, "national_id", ""),
            "phone": getattr(customer_obj, "mobile", ""),
            "email": getattr(customer_obj, "email", ""),
        },
        result_found=True,
        action=f"request:{key}",
        message=f"ref={ref}; role={role}; title={svc['title']}",
    )

    # إشعار داخلي تجريبي
    _send_notification(customer_obj, ref, svc["title"])

    messages.success(
        request,
        _(f"تم إنشاء الطلب: {svc['title']} — رقمك المرجعي: {ref}. تم إرسال إشعار عبر SMS/Email.")
    )
    return redirect("lookup:services")


# ===================== سجل الاستدعاءات =====================

@login_required(login_url=reverse_lazy("access:login"))
def lookup_history_view(request):
    qs = LookupHistory.objects.all().order_by("-id")

    qtext = (request.GET.get("q") or "").strip()
    t = (request.GET.get("type") or "").strip()
    r = request.GET.get("found")

    if qtext:
        qs = qs.filter(
            Q(query_value__icontains=qtext)
            | Q(full_name__icontains=qtext)
            | Q(phone__icontains=qtext)
            | Q(national_id__icontains=qtext)
            | Q(account_number__icontains=qtext)
            | Q(meter_number__icontains=qtext)
            | Q(unit_code__icontains=qtext)
            | Q(email__icontains=qtext)
        )
    if t:
        qs = qs.filter(query_type=t)
    if r in ("0", "1"):
        qs = qs.filter(result_found=(r == "1"))

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "lookup/history.html",
        {"page_obj": page_obj, "types": LookupHistory.QueryType.choices, "q": qtext, "t": t, "r": r},
    )
