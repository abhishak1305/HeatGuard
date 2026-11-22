from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import Lower


class Location(models.Model):
    """
    Represents a geographical monitoring station or city.
    """
    name = models.CharField(max_length=150, help_text="City or station name.")
    state_or_region = models.CharField(max_length=150, blank=True, help_text="State, province, or region.")
    country = models.CharField(max_length=100, default="Global", help_text="Country name.")
    latitude = models.DecimalField(
        max_digits=8,
        decimal_places=5,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text="Latitude in decimal degrees (-90.0 to 90.0)."
    )
    longitude = models.DecimalField(
        max_digits=8,
        decimal_places=5,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
        help_text="Longitude in decimal degrees (-180.0 to 180.0)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'country']
        indexes = [
            models.Index(fields=['name', 'country'], name='location_name_country_idx'),
            models.Index(fields=['latitude', 'longitude'], name='location_coordinates_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower('name'), Lower('state_or_region'), Lower('country'),
                name='unique_location_name_region_country_ci',
            ),
        ]
        verbose_name = "Location"
        verbose_name_plural = "Locations"

    def __str__(self):
        region_str = f", {self.state_or_region}" if self.state_or_region else ""
        return f"{self.name}{region_str} ({self.country})"


class WeatherRecord(models.Model):
    """
    Represents an observed or forecasted environmental telemetry record.
    Data provenance is strictly tracked.
    """
    RECORD_TYPE_CHOICES = [
        ('current', 'Current Observation'),
        ('forecast', 'Forecast Outlook'),
    ]

    RISK_LEVEL_CHOICES = [
        ('NORMAL', 'Normal'),
        ('CAUTION', 'Caution'),
        ('EXTREME_CAUTION', 'Extreme Caution'),
        ('DANGER', 'Danger'),
        ('EXTREME_DANGER', 'Extreme Danger'),
    ]

    DATA_SOURCE_CHOICES = [
        ('provider-supplied', 'Provider-Supplied (Open-Meteo)'),
        ('user-entered', 'User-Entered (Manual Report)'),
        ('application-calculated', 'Application-Calculated'),
        ('test-only', 'Test-Only Fixture'),
    ]

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='weather_records',
        help_text="Associated geographical monitoring location."
    )
    requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='weather_records',
        help_text="User who initiated or logged this record (optional, null for anonymous queries)."
    )
    recorded_at = models.DateTimeField(
        help_text="Timestamp of the weather reading or forecast target time."
    )
    retrieved_at = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when data was retrieved or calculated by the application."
    )
    record_type = models.CharField(
        max_length=20,
        choices=RECORD_TYPE_CHOICES,
        default='current'
    )
    temperature_c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Air temperature in degrees Celsius."
    )
    relative_humidity = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Relative humidity percentage (0.0 to 100.0%)."
    )
    provider_apparent_temp_c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional apparent temperature directly reported by the provider."
    )
    wind_speed_kmh = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
        help_text="Wind speed in km/h."
    )
    heat_index_c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Calculated Heat Index in degrees Celsius (where formula is valid)."
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        null=True,
        blank=True,
        help_text="Heat-risk category, or blank when required assessment inputs are unavailable."
    )
    data_source = models.CharField(
        max_length=30,
        choices=DATA_SOURCE_CHOICES,
        default='provider-supplied'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-created_at']
        indexes = [
            models.Index(fields=['recorded_at'], name='weather_recorded_at_idx'),
            models.Index(fields=['location', 'recorded_at'], name='weather_loc_recorded_idx'),
            models.Index(fields=['requested_by', 'recorded_at'], name='weather_user_recorded_idx'),
            models.Index(fields=['risk_level', 'recorded_at'], name='weather_risk_recorded_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['location', 'recorded_at'],
                condition=Q(record_type='current', data_source='provider-supplied'),
                name='unique_provider_observation_per_location_time',
            ),
        ]
        verbose_name = "Weather Record"
        verbose_name_plural = "Weather Records"

    def __str__(self):
        return f"{self.location.name} - {self.temperature_c}°C @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')} [{self.data_source}]"


class OfficialNotice(models.Model):
    """
    Represents an officially published heat advisory, watch, or emergency bulletin.
    """
    SEVERITY_CHOICES = [
        ('ADVISORY', 'Advisory'),
        ('WATCH', 'Watch'),
        ('WARNING', 'Warning'),
        ('EMERGENCY', 'Emergency'),
    ]

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='notices',
        help_text="Target location for this bulletin."
    )
    title = models.CharField(max_length=250, help_text="Title or summary headline of the notice.")
    message = models.TextField(help_text="Detailed advisory text and safety directives.")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='ADVISORY')
    issuing_organization = models.CharField(max_length=200, help_text="Issuing agency, e.g. National Weather Department.")
    source_url = models.URLField(
        help_text="Link to the original official publication; authorized staff must verify its authenticity."
    )
    issued_at = models.DateTimeField(default=timezone.now, help_text="Date and time when bulletin was issued.")
    valid_from = models.DateTimeField(help_text="Effective start time for this notice.")
    valid_until = models.DateTimeField(help_text="Effective expiration time for this notice.")
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='published_notices',
        help_text="Staff or admin user who published this record in HeatGuard."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True, help_text="Controls public visibility.")

    class Meta:
        ordering = ['-valid_from', '-created_at']
        indexes = [
            models.Index(fields=['is_published', 'valid_from', 'valid_until'], name='notice_published_window_idx'),
        ]
        verbose_name = "Official Notice"
        verbose_name_plural = "Official Notices"

    def clean(self):
        super().clean()
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({
                'valid_until': "The expiration date/time ('valid_until') must be strictly later than 'valid_from'."
            })
        if not self.source_url or not self.source_url.strip():
            raise ValidationError({
                'source_url': "An official notice requires a source URL. Authorized staff must verify its authenticity."
            })
        if not self.issuing_organization or not self.issuing_organization.strip():
            raise ValidationError({
                'issuing_organization': "An official notice requires an identified issuing organization."
            })

    @property
    def status(self):
        """Returns 'active', 'upcoming', or 'expired' based on timezone.now()."""
        now = timezone.now()
        if self.valid_until < now:
            return 'expired'
        elif self.valid_from > now:
            return 'upcoming'
        return 'active'

    def __str__(self):
        return f"[{self.severity}] {self.title} - {self.location.name} ({self.issuing_organization})"


class SavedLocation(models.Model):
    """
    Allows registered users to bookmark specific monitoring stations.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_locations'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='saved_by_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'location'], name='unique_user_saved_location')
        ]
        verbose_name = "Saved Location"
        verbose_name_plural = "Saved Locations"

    def __str__(self):
        return f"{self.user.username} saved {self.location.name}"
