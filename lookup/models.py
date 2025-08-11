from django.db import models

class LookupHistory(models.Model):
    query_type = models.CharField(max_length=50)  # نوع المعرف (عداد، حساب، هوية...)
    query_value = models.CharField(max_length=100)  # القيمة التي تم البحث بها
    result_found = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.query_type}: {self.query_value} ({'Found' if self.result_found else 'Not Found'})"
