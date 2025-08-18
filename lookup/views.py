# lookup/views.py
from __future__ import annotations

from typing import Dict, Optional
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from .models import Customer, LookupHistory


# ===================== أدوات مساعدة =====================
def _digits(s: Optional[str]) -> str:
    """أرقام فقط (يتعامل مع None)."""
    return "".join(ch for ch in (s or "").strip() if ch.isdigit())


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
    if data.get("email"):
        return LookupHistory.QueryType.EMAIL
    if data.get("full_name"):
        return LookupHistory.QueryType.NAME
    return LookupHistory.QueryType.UNKNOWN


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
                or data.get("email")
                or data.get("full_name")
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


# ===================== استدعاء البيانات =====================
@login_required(login_url=reverse_lazy("access:login"))
def data_lookup_view(request):
    """
    - يقبل معرّف واحد على الأقل.
    - لو تطابق واحد → تحويل إلى اختيار الدور.
    - لو عدة نتائج → عرضها.
    - لو لا يوجد → رسالة.
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

    results_qs = None
    selected = None

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

        # تحقق من الإدخالات
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

        # ابحث
        q = Q()
        if data["full_name"]: q &= Q(full_name__icontains=data["full_name"])
        if data["meter_number"]: q &= Q(meter_no__iexact=data["meter_number"])
        if data["account_number"]: q &= Q(account_no__iexact=data["account_number"])
        if data["national_id"]: q &= Q(national_id__iexact=data["national_id"])
        if data["phone"]: q &= Q(mobile__iexact=data["phone"])
        if data["unit_code"]: q &= Q(unit_code__iexact=data["unit_code"])
        if data["email"]: q &= Q(email__iexact=data["email"])

        queryset = Customer.objects.filter(q)
        count = queryset.count()

        if count == 0:
            messages.warning(request, _("لا نتائج مطابقة."))
            _log_lookup(request, data, result_found=False, action=action, message=_("لا نتائج."))
            return render(request, "lookup/data_lookup.html", {"data": {**initial, **data}, "errors": {}})

        if count == 1:
            selected = queryset.first()
            _log_lookup(request, data, result_found=True, action=action, message=_("تطابق واحد."))
            request.session["customer_id"] = selected.id
            return redirect("lookup:role_select")

        # لو نتائج متعددة
        results_qs = queryset.only("full_name", "account_no", "national_id", "mobile", "unit_code")[:50]
        messages.success(request, _(f"عدد النتائج: {count} (المعروض: {results_qs.count()})"))
        _log_lookup(request, data, result_found=True, action=action, message=_("نتائج متعددة."))

        return render(request, "lookup/data_lookup.html", {
            "data": {**initial, **data}, "errors": {}, "results": results_qs, "selected": None,
        })

    # GET
    return render(request, "lookup/data_lookup.html", {"data": initial, "errors": {}, "results": None, "selected": None})


# ===================== اختيار الدور =====================
@login_required(login_url=reverse_lazy("access:login"))
def role_select_view(request):
    cid = request.session.get("customer_id")
    if not cid:
        return redirect("lookup:home")
    customer = get_object_or_404(Customer, id=cid)

    if request.method == "POST":
        role = request.POST.get("role")
        if role in ("beneficiary", "owner"):
            request.session["role"] = role
            return redirect("lookup:services_page")

    return render(request, "lookup/role_select.html", {"customer": customer})


# ===================== صفحة الخدمات =====================
@login_required(login_url=reverse_lazy("access:login"))
def services_page_view(request):
    cid = request.session.get("customer_id")
    role = request.session.get("role")
    if not cid or role not in ("beneficiary", "owner"):
        return redirect("lookup:home")
    customer = get_object_or_404(Customer, id=cid)
    template = "lookup/services_beneficiary.html" if role == "beneficiary" else "lookup/services_owner.html"
    return render(request, template, {"customer": customer, "role": role})


# ===================== سجل الاستدعاءات =====================
@login_required(login_url=reverse_lazy("access:login"))
def lookup_history_view(request):
    qs = LookupHistory.objects.all()
    qtext = (request.GET.get("q") or "").strip()
    t = (request.GET.get("type") or "").strip()
    r = request.GET.get("found")

    if qtext:
        qs = qs.filter(
            Q(query_value__icontains=qtext) |
            Q(full_name__icontains=qtext) |
            Q(phone__icontains=qtext) |
            Q(national_id__icontains=qtext) |
            Q(account_number__icontains=qtext) |
            Q(meter_number__icontains=qtext) |
            Q(unit_code__icontains=qtext) |
            Q(email__icontains=qtext)
        )
    if t:
        qs = qs.filter(query_type=t)
    if r in ("0", "1"):
        qs = qs.filter(result_found=(r == "1"))

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "lookup/history.html", {
        "page_obj": page_obj,
        "types": LookupHistory.QueryType.choices,
        "q": qtext, "t": t, "r": r,
    })
