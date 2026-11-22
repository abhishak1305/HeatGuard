from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('search/', views.city_search_view, name='city_search'),
    path('city/<int:location_id>/', views.city_dashboard_view, name='city_dashboard'),
    path('forecast/', views.forecast_view, name='forecast'),
    path('india-heatmap/', views.india_heatmap_view, name='india_heatmap'),
    path('india-heatmap/data/', views.india_heatmap_data_view, name='india_heatmap_data'),
    path('history/', views.weather_history_view, name='weather_history'),
    path('history/export.csv', views.weather_history_export_view, name='weather_history_export'),
    path('observations/report/', views.manual_observation_view, name='manual_observation'),
    path('comparison/', views.city_comparison_view, name='city_comparison'),
    path('safety-guidance/', views.safety_guidance_view, name='safety_guidance'),
    
    # Official Notices & Staff Dashboard
    path('notices/', views.notice_list_view, name='notice_list'),
    path('notices/create/', views.notice_create_view, name='notice_create'),
    path('notices/<int:notice_id>/edit/', views.notice_edit_view, name='notice_edit'),
    path('staff/dashboard/', views.staff_dashboard_view, name='staff_dashboard'),
    
    # Preferences (Cookies)
    path('preferences/unit/', views.set_temperature_unit_view, name='set_temperature_unit'),
    
    # Authentication & User Profile
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/profile/', views.profile_view, name='profile'),
    path('locations/<int:location_id>/save/', views.save_location_view, name='save_location'),
    path('locations/<int:location_id>/remove/', views.remove_saved_location_view, name='remove_saved_location'),
]
