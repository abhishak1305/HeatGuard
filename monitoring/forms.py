from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .models import OfficialNotice, Location, WeatherRecord


class HeatGuardRegistrationForm(UserCreationForm):
    """
    Standard user registration form subclassing Django's UserCreationForm.
    Collects username, optional email, and passwords handled by Django's configured hasher (PBKDF2 by default).
    """
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Optional email address'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Choose a username'})
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Optional email address'})
        for name, field in self.fields.items():
            if 'password' in name.lower() or (field.label and 'password' in field.label.lower()):
                field.widget.attrs.update({'class': 'form-input', 'placeholder': 'Enter a secure password'})


class HeatGuardLoginForm(AuthenticationForm):
    """
    Standard login authentication form using Django's AuthenticationForm.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Enter your username'})
        self.fields['password'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Enter your password'})


class CitySearchForm(forms.Form):
    """
    Form for validating read-only city / monitoring station search queries via HTTP GET.
    """
    city = forms.CharField(
        label="City or Station Name",
        max_length=100,
        min_length=2,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter city or station name (e.g. Central, Coastal)...',
            'autocomplete': 'off',
            'aria-label': 'City or station name'
        }),
        error_messages={
            'required': "Please enter a city or station name.",
            'min_length': "Search query must be at least 2 characters long.",
            'max_length': "Search query cannot exceed 100 characters.",
        }
    )

    def clean_city(self):
        city = self.cleaned_data.get('city', '').strip()
        normalized_city = " ".join(city.split())

        if len(normalized_city) < 2:
            raise ValidationError("Search query must contain at least 2 non-whitespace characters.")

        return normalized_city


class CityComparisonForm(forms.Form):
    """
    Form allowing users to compare 2 or 3 cities.
    Users can select existing stations from a dropdown, OR type city names to be resolved/geocoded.
    """
    station_1 = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        empty_label="-- Select an existing station --",
        label="Station 1 (Select)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    city_name_1 = forms.CharField(
        required=False,
        max_length=100,
        label="Or City 1 (Search name)",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. London'})
    )

    station_2 = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        empty_label="-- Select an existing station --",
        label="Station 2 (Select)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    city_name_2 = forms.CharField(
        required=False,
        max_length=100,
        label="Or City 2 (Search name)",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Madrid'})
    )

    station_3 = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        empty_label="-- Optional Station 3 --",
        label="Station 3 (Optional)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    city_name_3 = forms.CharField(
        required=False,
        max_length=100,
        label="Or City 3 (Search name)",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Cairo (optional)'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Location.objects.all().order_by('name')
        self.fields['station_1'].queryset = qs
        self.fields['station_2'].queryset = qs
        self.fields['station_3'].queryset = qs

    def clean(self):
        cleaned_data = super().clean()
        st1 = cleaned_data.get('station_1')
        c1 = (cleaned_data.get('city_name_1') or '').strip()

        st2 = cleaned_data.get('station_2')
        c2 = (cleaned_data.get('city_name_2') or '').strip()

        if not st1 and not c1:
            self.add_error('station_1', "Please select an existing station or enter a city name for Location 1.")

        if not st2 and not c2:
            self.add_error('station_2', "Please select an existing station or enter a city name for Location 2.")

        return cleaned_data


class OfficialNoticeForm(forms.ModelForm):
    """
    ModelForm for authorized staff to create or edit Official Notices.
    """
    issued_at = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'], initial=timezone.localtime,
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-input', 'type': 'datetime-local'},
        ),
    )

    valid_from = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-input', 'type': 'datetime-local'},
        ),
    )
    valid_until = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-input', 'type': 'datetime-local'},
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_url'].help_text = (
            "HeatGuard validates URL format only. Confirm that this is the issuing authority's "
            "authentic publication page before publishing."
        )

    class Meta:
        model = OfficialNotice
        fields = [
            'location',
            'title',
            'severity',
            'issuing_organization',
            'source_url',
            'issued_at',
            'valid_from',
            'valid_until',
            'message',
            'is_published',
        ]
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Red Heatwave Warning for Urban Zone'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'issuing_organization': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. India Meteorological Department (IMD)'}),
            'source_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://mausam.imd.gov.in/...'}),
            'message': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Official advisory directives, affected population, precautions...'}),
            'is_published': forms.CheckboxInput(attrs={'style': 'margin-right: 0.5rem;'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')
        issued_at = cleaned_data.get('issued_at')
        source_url = cleaned_data.get('source_url')
        issuing_org = cleaned_data.get('issuing_organization')

        if valid_from and valid_until and valid_until <= valid_from:
            self.add_error('valid_until', "The expiration date/time ('valid_until') must be strictly later than 'valid_from'.")

        if issued_at and valid_until and issued_at > valid_until:
            self.add_error('issued_at', "The issue time cannot be later than the notice expiration time.")

        if not source_url:
            self.add_error('source_url', "An official notice requires a source URL. Staff must verify its authenticity.")

        if not issuing_org or not issuing_org.strip():
            self.add_error('issuing_organization', "An official notice requires an identified issuing organization.")

        return cleaned_data
class WeatherHistoryFilterForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=Location.objects.order_by('name', 'country'), required=False,
        empty_label='All locations', widget=forms.Select(attrs={'class': 'form-select'}),
    )
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}))
    risk_level = forms.ChoiceField(
        required=False,
        choices=[('', 'All risk levels'), *WeatherRecord.RISK_LEVEL_CHOICES],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', 'The end date must be on or after the start date.')
        return cleaned_data


class ManualObservationForm(forms.ModelForm):
    temperature_c = forms.DecimalField(
        min_value=-50, max_value=65, max_digits=5, decimal_places=2,
        label='Temperature (°C)',
        validators=[MinValueValidator(-50), MaxValueValidator(65)],
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.1'}),
    )
    relative_humidity = forms.DecimalField(
        min_value=0, max_value=100, max_digits=5, decimal_places=2,
        label='Relative humidity (%)',
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.1'}),
    )

    class Meta:
        model = WeatherRecord
        fields = ('location', 'temperature_c', 'relative_humidity')
        labels = {'location': 'Monitoring location'}
        widgets = {'location': forms.Select(attrs={'class': 'form-select'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.order_by('name', 'country')
