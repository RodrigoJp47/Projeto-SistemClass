# from django.contrib import admin
# from django.urls import path, include

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('', include('accounts.urls')),
# ]
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('crm/', include('crm.urls')),
    path('tarefas/', include('core.urls')),
    path('relatorios/', include('relatorios.urls')),
    path('notas_fiscais/', include('notas_fiscais.urls')),
    path('pdv/', include('pdv.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)