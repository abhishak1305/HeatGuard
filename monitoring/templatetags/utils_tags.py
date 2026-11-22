from django import template

register = template.Library()


def _to_float(value):
    """Best-effort conversion of a Decimal/int/str to float; None on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@register.filter
def temp_display(value, unit='C'):
    """
    Render a temperature stored in Celsius using the visitor's preferred unit.

    Usage: {{ temperature_c|temp_display:temp_unit }}

    Output format matches the previous template markup ("36.5 °C") so that
    existing pages and tests keep the same wording.
    """
    val = _to_float(value)
    if val is None:
        return "Not available"

    if unit == 'F':
        return f"{(val * 9.0 / 5.0) + 32.0:.1f} °F"
    return f"{val:.1f} °C"


