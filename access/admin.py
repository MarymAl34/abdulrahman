from django.contrib import admin
from .models import AccessLog

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    # أعمدة القائمة
    list_display = ("user_identifier", "display_action", "timestamp", "ip_address")
    list_filter = ("action",)
    search_fields = ("user_identifier", "ip_address", "user_agent")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    # قراءة فقط (لأن السجلات تُنشأ آليًا)
    readonly_fields = ("user_identifier", "action", "timestamp", "ip_address", "user_agent")

    fieldsets = (
        (None, {
            "fields": ("user_identifier", "action", "timestamp"),
        }),
        ("تفاصيل إضافية", {
            "fields": ("ip_address", "user_agent"),
            "classes": ("collapse",),
        }),
    )

    # عرض اسم الإجراء بالعربي بدل القيمة الخام
    def display_action(self, obj):
        return obj.get_action_display()
    display_action.short_description = "الإجراء"

    # منع الإضافة/التعديل اليدوي
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
