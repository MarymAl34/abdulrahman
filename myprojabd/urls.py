from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # روابط التطبيقات المخصصة
    path('access/', include('access.urls')),
    path('lookup/', include('lookup.urls')),
    path('tickets/', include('tickets.urls')),

    # الجذر → تحويل إلى lookup/
    path('', RedirectView.as_view(url='/lookup/', permanent=False)),
]
