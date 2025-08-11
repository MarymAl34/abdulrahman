from django.contrib import admin
from .models import AccessLog

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ("user_identifier", "action", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("user_identifier", "action")
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)
