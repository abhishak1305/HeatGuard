from django.contrib.auth.models import AnonymousUser
from .permissions import user_can, can_manage_notices


def temperature_unit(request):
    """
    Context processor that provides the temperature display unit preference.
    Reads the 'heatguard_temp_unit' cookie set by the set_temperature_unit view.
    Returns 'C' by default if the cookie is not set.
    """
    unit = request.COOKIES.get('heatguard_temp_unit', 'C').upper()
    user = getattr(request, 'user', AnonymousUser())
    return {
        'temp_unit': unit if unit in {'C', 'F'} else 'C',
        'can_manage_notices': can_manage_notices(user),
        'can_add_notice': user_can(user, 'monitoring.add_officialnotice'),
        'can_change_notice': user_can(user, 'monitoring.change_officialnotice'),
    }
