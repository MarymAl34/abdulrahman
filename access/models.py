from django.db import models

class AccessLog(models.Model):
    user_identifier = models.CharField(max_length=100)  # مثلاً: رقم جوال أو إيميل
    action = models.CharField(max_length=50)  # نوع الحدث (تسجيل دخول، خروج...)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_identifier} - {self.action} - {self.timestamp}"
