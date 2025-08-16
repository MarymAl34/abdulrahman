from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # روابط التطبيقات المخصصة
    path('access/', include('access.urls')),
    path('lookup/', include('lookup.urls')),
    path('tickets/', include('tickets.urls')),

    # الجذر → تحويل إلى صفحة إنشاء الحساب
    path('', RedirectView.as_view(url='/access/signup/', permanent=False)),
]

# خدمة ملفات الوسائط أثناء التطوير
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
