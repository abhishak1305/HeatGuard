from django.contrib import admin
from django.urls import path, include
from monitoring import views as monitoring_views

handler400 = monitoring_views.bad_request_view
handler403 = monitoring_views.permission_denied_view
handler404 = monitoring_views.page_not_found_view
handler500 = monitoring_views.server_error_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('monitoring.urls')),
]
