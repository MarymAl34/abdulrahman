from django.contrib import admin
from .models import LookupHistory

@admin.register(LookupHistory)
class LookupHistoryAdmin(admin.ModelAdmin):
    list_display = ("query_type", "query_value", "result_found", "timestamp")
    list_filter = ("query_type", "result_found", "timestamp")
    search_fields = ("query_value",)
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)
