from django.contrib import admin
from django import forms
from .models import Location, WeatherRecord, OfficialNotice, SavedLocation


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'state_or_region', 'country', 'latitude', 'longitude', 'created_at')
    list_filter = ('country', 'state_or_region')
    search_fields = ('name', 'state_or_region', 'country')
    date_hierarchy = 'created_at'
    ordering = ('name',)


class WeatherRecordAdminForm(forms.ModelForm):
    class Meta:
        model = WeatherRecord
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_source'].help_text = (
            'Select the actual provenance for this record. Do not label a manual entry as provider-supplied.'
        )
        if self.instance._state.adding:
            self.fields['data_source'].initial = ''


@admin.register(WeatherRecord)
class WeatherRecordAdmin(admin.ModelAdmin):
    form = WeatherRecordAdminForm
    list_select_related = ('location', 'requested_by')
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
    list_select_related = ('location', 'created_by')
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
    list_select_related = ('user', 'location')
    list_display = ('user', 'location', 'created_at')
    list_filter = ('created_at', 'location__country')
    search_fields = ('user__username', 'location__name')
    date_hierarchy = 'created_at'
