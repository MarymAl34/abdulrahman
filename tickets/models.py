from django.db import models

class Ticket(models.Model):
    reference_number = models.CharField(max_length=20, unique=True)  # رقم مرجعي فريد
    ticket_type = models.CharField(max_length=50)  # نوع الطلب
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="Pending")  # الحالة الحالية

    def __str__(self):
        return f"{self.reference_number} - {self.ticket_type} - {self.status}"
