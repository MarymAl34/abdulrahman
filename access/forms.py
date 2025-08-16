# access/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

ksa_id_validator = RegexValidator(r'^\d{10}$', "رقم الهوية يجب أن يكون 10 أرقام.")
phone_validator  = RegexValidator(r'^05\d{8}$', "رقم الجوال بصيغة سعودية مثل 05XXXXXXXX.")

class SignupForm(forms.ModelForm):
    phone_number = forms.CharField(
        max_length=10,
        validators=[phone_validator],
        label="رقم الجوال"
    )
    national_id = forms.CharField(
        max_length=10,
        validators=[ksa_id_validator],
        label="رقم الهوية"
    )
    password1 = forms.CharField(widget=forms.PasswordInput, label="كلمة المرور")
    password2 = forms.CharField(widget=forms.PasswordInput, label="تأكيد كلمة المرور")

    class Meta:
        model = User
        # عدّل الأسماء حسب موديل المستخدم عندك
        fields = ["phone_number", "national_id"]

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 != p2:
            self.add_error("password2", "كلمتا المرور غير متطابقتين.")
        if p1:
            validate_password(p1)  # يستخدم مدققات Django القياسية
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        # لو موديلك ما يستخدم username، احذف السطر التالي
        if hasattr(user, "username") and not user.username:
            user.username = self.cleaned_data["phone_number"]
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
