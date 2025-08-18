# lookup/management/commands/import_customers.py
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
import pandas as pd

from lookup.models import Customer

# حجم الدفعة في عمليات الإنشاء/التحديث الجماعي
CHUNK = 1000

# خرائط أسماء الأعمدة المحتملة (عدّلها لتطابق رؤوس ملفك إن لزم)
COLMAP = {
    "full_name":   ["الاسم", "name", "Full Name"],
    "meter_no":    ["رقم العداد", "meter_no", "Meter"],
    "account_no":  ["رقم الحساب", "account_no", "Account"],
    "national_id": ["رقم الهوية", "national_id", "ID"],
    "mobile":      ["رقم الجوال", "mobile", "Phone", "جوال"],
    "unit_code":   ["كود الوحدة", "unit_code", "Unit"],
    "email":       ["البريد الإلكتروني", "email", "Email"],
}

# مفاتيح تعريف قوية نستخدمها للمطابقة/التحديث
KEYS = ("account_no", "national_id", "meter_no", "mobile", "unit_code", "email")


def _resolve_columns(df: pd.DataFrame) -> dict:
    """حدد عمود كل حقل من رؤوس الأعمدة الفعلية."""
    resolved = {}
    for field, candidates in COLMAP.items():
        for c in candidates:
            if c in df.columns:
                resolved[field] = c
                break
    return resolved


def _norm(val) -> str:
    """تنظيف/تطبيع بسيط للقيم النصية."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return s


class Command(BaseCommand):
    help = "استيراد العملاء من ملف Excel/CSV إلى قاعدة البيانات بسرعة وأمان"

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            nargs="?",
            default=str(Path(settings.BASE_DIR, "data_files", "customers.xlsx")),
            help="مسار الملف (افتراضي data_files/customers.xlsx)",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="حذف كل السجلات القديمة قبل الاستيراد (الأسرع إذا كان الملف هو المصدر الوحيد).",
        )

    def handle(self, *args, **opts):
        path = Path(opts["path"]).resolve()
        if not path.exists():
            raise CommandError(f"الملف غير موجود: {path}")
        if path.stat().st_size == 0:
            raise CommandError(f"الملف موجود لكنه فارغ: {path}")

        # حاول قراءة XLSX أولًا، وإن فشل جرّب CSV تلقائيًا
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception:
            try:
                df = pd.read_csv(path, encoding_errors="replace")
            except Exception as e:
                raise CommandError(f"فشل قراءة الملف كـ XLSX وCSV: {e}")

        if df.empty:
            raise CommandError("الملف لا يحتوي على صفوف بيانات.")

        df = df.fillna("")
        resolved = _resolve_columns(df)
        if not resolved:
            heads = ", ".join(map(str, df.columns))
            raise CommandError(
                "تعذرت مطابقة الأعمدة. عدّل COLMAP أو سمِّي الأعمدة لتطابق القيم المتوقعة.\n"
                f"رؤوس ملفك الحالية: {heads}"
            )

        # حوّل الداتا لقائمة قواميس منظّفة
        rows: list[dict] = []
        for _, row in df.iterrows():
            rec = {}
            for field, col in resolved.items():
                rec[field] = _norm(row[col])
            # تجاهل الصفوف الفارغة تمامًا
            if any(rec.values()):
                rows.append(rec)

        if not rows:
            raise CommandError("بعد التنظيف، لا توجد صفوف صالحة للاستيراد.")

        deleted = created = updated = 0

        # أسرع سيناريو: حذف ثم إنشاء جماعي
        if opts["truncate"]:
            deleted = Customer.objects.all().delete()[0]
            self.stdout.write(f"حذف السجلات القديمة: {deleted}")

            objs = [Customer(**rec) for rec in rows]
            for i in range(0, len(objs), CHUNK):
                Customer.objects.bulk_create(objs[i:i + CHUNK])
                self.stdout.write(f"إدراج: {min(i + CHUNK, len(objs))}/{len(objs)}")
            created = len(objs)

        else:
            # بناء خرائط للسجلات الحالية لاستخدامها كمفاتيح مطابقة
            existing_maps: dict[str, dict[str, int]] = {k: {} for k in KEYS}
            qs = Customer.objects.all().only("id", *KEYS)
            for obj in qs.iterator(chunk_size=CHUNK):
                for k in KEYS:
                    v = getattr(obj, k)
                    if v:
                        existing_maps[k][v] = obj.id

            to_create, to_update = [], []

            for rec in rows:
                # ابحث بأول مفتاح قوي متوفر في السجل
                found_id = None
                for k in KEYS:
                    v = rec.get(k)
                    if v and v in existing_maps[k]:
                        found_id = existing_maps[k][v]
                        break

                if found_id:
                    obj = Customer(**rec)
                    obj.id = found_id
                    to_update.append(obj)
                else:
                    to_create.append(Customer(**rec))

            # إنشاء جماعي
            for i in range(0, len(to_create), CHUNK):
                Customer.objects.bulk_create(to_create[i:i + CHUNK])
                created += len(to_create[i:i + CHUNK])
                self.stdout.write(f"إنشاء: {created}/{len(to_create)}")

            # تحديث جماعي (فقط الحقول القابلة للتغيير)
            if to_update:
                fields = ["full_name", "meter_no", "account_no", "national_id", "mobile", "unit_code", "email"]
                for i in range(0, len(to_update), CHUNK):
                    Customer.objects.bulk_update(to_update[i:i + CHUNK], fields=fields)
                    updated += len(to_update[i:i + CHUNK])
                    self.stdout.write(f"تحديث: {updated}/{len(to_update)}")

        self.stdout.write(self.style.SUCCESS(
            f"تم الاستيراد بنجاح — حذف: {deleted} | أضيف: {created} | تحديث: {updated}"
        ))
