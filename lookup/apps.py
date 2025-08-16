from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class LookupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lookup'
    verbose_name = _('استدعاء البيانات')
