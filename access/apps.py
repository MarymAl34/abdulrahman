from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AccessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'access'
    verbose_name = _('الوصول وإدارة الدخول')
