from django.db import models
from django.utils.translation import gettext_lazy as _

class Ticket(models.Model):
    reference_number = models.CharField(_("الرقم المرجعي"), max_length=20, unique=True)  # رقم مرجعي فريد
    ticket_type = models.CharField(_("نوع الطلب"), max_length=50)
    created_at = models.DateTimeField(_("تاريخ الإنشاء"), auto_now_add=True)
    status = models.CharField(_("الحالة الحالية"), max_length=20, default="Pending")

    class Meta:
        verbose_name = _("طلب")
        verbose_name_plural = _("الطلبات")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference_number} - {self.ticket_type} - {self.status}"
