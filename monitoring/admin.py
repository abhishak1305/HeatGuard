from django.contrib import admin
from .models import Location, WeatherRecord, OfficialNotice, SavedLocation


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'state_or_region', 'country', 'latitude', 'longitude', 'created_at')
    list_filter = ('country', 'state_or_region')
    search_fields = ('name', 'state_or_region', 'country')
    date_hierarchy = 'created_at'
    ordering = ('name',)


@admin.register(WeatherRecord)
class WeatherRecordAdmin(admin.ModelAdmin):
    list_display = (
        'location',
        'record_type',
        'temperature_c',
        'relative_humidity',
        'heat_index_c',
        'risk_level',
        'data_source',
        'recorded_at',
        'requested_by'
    )
    list_filter = ('record_type', 'risk_level', 'data_source', 'location__country')
    search_fields = ('location__name', 'location__state_or_region', 'requested_by__username')
    date_hierarchy = 'recorded_at'
    readonly_fields = ('created_at', 'retrieved_at')


@admin.register(OfficialNotice)
class OfficialNoticeAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'location',
        'severity',
        'issuing_organization',
        'valid_from',
        'valid_until',
        'is_published',
        'created_by'
    )
    list_filter = ('severity', 'is_published', 'issuing_organization', 'location')
    search_fields = ('title', 'message', 'issuing_organization', 'location__name')
    date_hierarchy = 'valid_from'
    readonly_fields = ('created_at',)


@admin.register(SavedLocation)
class SavedLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'created_at')
    list_filter = ('created_at', 'location__country')
    search_fields = ('user__username', 'location__name')
    date_hierarchy = 'created_at'
