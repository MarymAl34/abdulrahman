# access/views.py
import os
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import UserProfile, AccessLog, OTPRequest

# -------------------- إعدادات عامة --------------------
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_DEV_CODE = "111111"  # كود ثابت للتجربة في وضع التطوير

User = get_user_model()


# -------------------- أدوات مساعدة --------------------
def normalize_phone(raw: str) -> str:
    """تنظيف رقم الجوال إلى أرقام فقط."""
    return "".join(ch for ch in (raw or "").strip() if ch.isdigit())


def otp_bypass_enabled() -> bool:
    """
    تفعيل وضع التجربة للـ OTP إذا:
    - DEBUG=True في الإعدادات، أو
    - متغير البيئة OTP_BYPASS=1
    """
    return bool(getattr(settings, "DEBUG", False) or os.environ.get("OTP_BYPASS") == "1")


def send_otp_sms(phone: str, code: str) -> bool:
    """
    إرسال OTP عبر Unifonic.
    - إذا وضع التجربة مفعّل، نرجّع True بدون إرسال فعلي.
    يلزم (للإرسال الحقيقي):
      UNIFONIC_API_KEY
      UNIFONIC_SENDER (اختياري، الافتراضي 'OTP')
    """
    if otp_bypass_enabled():
        # وضع التطوير: لا ترسل شيء، اعتبره نجح
        print(f"[DEV] OTP for {phone}: {code}")
        return True

    api_key = os.environ.get("UNIFONIC_API_KEY")
    sender = os.environ.get("UNIFONIC_SENDER", "OTP")
    if not api_key:
        print("[ERROR] UNIFONIC_API_KEY غير مضبوط")
        return False

    try:
        url = "https://el.cloud.unifonic.com/rest/SMS/messages"
        payload = {
            "AppSid": api_key,
            "Recipient": phone,
            "Body": f"رمز التحقق الخاص بك: {code}",
            "SenderID": sender,
        }
        res = requests.post(url, data=payload, timeout=10)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"[ERROR] فشل إرسال OTP عبر Unifonic: {e}")
        return False


def phone_valid(phone: str) -> bool:
    """تحقق مبدئي: طول منطقي (سعودي عادة 10 أرقام)"""
    return phone.isdigit() and 9 <= len(phone) <= 15


def national_id_valid(national_id: str) -> bool:
    """رقم هوية سعودي: 10 أرقام."""
    return national_id.isdigit() and len(national_id) == 10


# -------------------- تسجيل حساب جديد --------------------
def signup_view(request):
    if request.method == "POST":
        phone = normalize_phone(request.POST.get("phone"))
        national_id = (request.POST.get("national_id") or "").strip()
        password = request.POST.get("password") or ""

        # تحقق من المدخلات
        if not phone_valid(phone):
            messages.error(request, "رقم الجوال غير صالح.")
            return render(request, "access/signup.html")

        if not national_id_valid(national_id):
            messages.error(request, "رقم الهوية يجب أن يكون 10 أرقام.")
            return render(request, "access/signup.html")

        try:
            validate_password(password)
        except Exception as e:
            # عرض أول رسالة خطأ من مدققات كلمة المرور
            msg = ", ".join([str(x) for x in e.messages]) if hasattr(e, "messages") else "كلمة المرور غير صالحة."
            messages.error(request, msg)
            return render(request, "access/signup.html")

        # هل الرقم مسجّل؟
        if User.objects.filter(username=phone).exists():
            messages.error(request, "هذا الرقم مسجّل بالفعل. يمكنك تسجيل الدخول.")
            return redirect("access:login")

        # تبريد إعادة الإرسال
        last = OTPRequest.objects.filter(phone=phone).order_by("-created_at").first()
        if last and (timezone.now() - last.created_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
            remaining = OTP_RESEND_COOLDOWN_SECONDS - int((timezone.now() - last.created_at).total_seconds())
            messages.error(request, f"انتظر {remaining} ثانية قبل طلب رمز جديد.")
            return render(request, "access/signup.html")

        # حفظ البيانات مؤقتاً في الجلسة
        request.session["pending_signup"] = {
            "phone": phone,
            "national_id": national_id,
            "password": password,
            "ts": timezone.now().isoformat(),
        }

        # إنشاء وإرسال OTP
        code = OTPRequest.generate_code()
        if otp_bypass_enabled():
            code = OTP_DEV_CODE  # كود ثابت للتجارب
        OTPRequest.objects.create(phone=phone, code=code)

        if not send_otp_sms(phone, code):
            messages.error(request, "تعذر إرسال رمز التحقق. حاول لاحقًا.")
            return render(request, "access/signup.html")

        messages.success(request, "تم إرسال رمز التحقق إلى جوالك.")
        return redirect("access:verify_otp")

    return render(request, "access/signup.html")


# -------------------- التحقق من OTP --------------------
def verify_otp_view(request):
    pending = request.session.get("pending_signup")
    if not pending:
        messages.error(request, "انتهت الجلسة. ابدأ التسجيل من جديد.")
        return redirect("access:signup")

    phone = pending["phone"]

    # إعادة إرسال
    if request.method == "POST" and request.POST.get("resend") == "1":
        last = OTPRequest.objects.filter(phone=phone).order_by("-created_at").first()
        if last and (timezone.now() - last.created_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
            remaining = OTP_RESEND_COOLDOWN_SECONDS - int((timezone.now() - last.created_at).total_seconds())
            messages.error(request, f"انتظر {remaining} ثانية قبل طلب رمز جديد.")
            return redirect("access:verify_otp")

        code = OTPRequest.generate_code()
        if otp_bypass_enabled():
            code = OTP_DEV_CODE
        OTPRequest.objects.create(phone=phone, code=code)

        if not send_otp_sms(phone, code):
            messages.error(request, "تعذر إرسال رمز التحقق.")
            return redirect("access:verify_otp")

        messages.success(request, "تم إرسال رمز تحقق جديد.")
        return redirect("access:verify_otp")

    # تحقق من الرمز المدخل
    if request.method == "POST" and request.POST.get("resend") != "1":
        code = (request.POST.get("code") or "").strip()
        record = OTPRequest.objects.filter(phone=phone).order_by("-created_at").first()

        if not record or not record.is_valid():
            messages.error(request, "الرمز غير صالح أو منتهي.")
            return redirect("access:verify_otp")

        # في وضع التطوير نقبل الكود الثابت
        expected = OTP_DEV_CODE if otp_bypass_enabled() else record.code
        if expected != code:
            messages.error(request, "رمز التحقق غير صحيح.")
            return redirect("access:verify_otp")

        # إنشاء المستخدم
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=phone,
                    password=pending["password"],
                )
                UserProfile.objects.create(
                    user=user,
                    phone=phone,
                    national_id=pending["national_id"],
                )
        except IntegrityError:
            messages.error(request, "هذا الرقم مسجّل بالفعل.")
            return redirect("access:login")

        # تسجيل الدخول مباشرة
        login(request, user)
        request.session.pop("pending_signup", None)

        # تسجيل الحدث
        AccessLog.objects.create(
            user_identifier=phone,
            action=AccessLog.Actions.LOGIN,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )

        messages.success(request, "تم إنشاء الحساب وتسجيل الدخول.")
        return redirect("/lookup/")

    return render(request, "access/verify_otp.html", {"phone": phone})


# -------------------- تسجيل الدخول --------------------
def login_view(request):
    if request.method == "POST":
        phone = normalize_phone(request.POST.get("phone"))
        password = request.POST.get("password") or ""

        if not phone or not password:
            messages.error(request, "أدخل رقم الجوال وكلمة المرور.")
            return render(request, "access/login.html")

        user = authenticate(request, username=phone, password=password)
        if not user:
            messages.error(request, "بيانات الدخول غير صحيحة.")
            return render(request, "access/login.html")

        login(request, user)

        AccessLog.objects.create(
            user_identifier=phone,
            action=AccessLog.Actions.LOGIN,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )

        messages.success(request, "تم تسجيل الدخول بنجاح ✅")
        return redirect("/lookup/")

    return render(request, "access/login.html")


# -------------------- تسجيل الخروج --------------------
def logout_view(request):
    logout(request)
    messages.success(request, "تم تسجيل الخروج.")
    return redirect("access:login")
