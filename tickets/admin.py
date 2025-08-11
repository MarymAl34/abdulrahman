from django.contrib import admin
from .models import Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "ticket_type", "status", "created_at")
    list_filter = ("ticket_type", "status", "created_at")
    search_fields = ("reference_number", "ticket_type")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
