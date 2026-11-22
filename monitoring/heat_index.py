"""
HeatGuard Heat Index Calculation and Thermal Risk Evaluation Module.

Reference:
    National Oceanic and Atmospheric Administration (NOAA) / National Weather Service (NWS)
    Weather Prediction Center (WPC) Heat Index Equation:
    https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
    and NOAA Technical Report NWS SR 90-23 (Rothfusz, 1990).

CRITICAL SCIENTIFIC & METHODOLOGY NOTES:
1. Nature of Metric:
   This calculation produces a Heat Index-based apparent-temperature estimate.
   It represents how warm the air feels to the human body in shade with light air movement.
   IT IS NOT Wet Bulb Globe Temperature (WBGT) and MUST NOT be described as a certified
   medical or workplace physiological human thermal stress measurement.
   WBGT incorporates direct solar radiation load, solar angle, cloud cover, and wind velocity.

2. Applicable Input Ranges:
   - Temperature (°C): The implementation accepts values from -50°C to 65°C.
   - Relative Humidity (%): Valid 0.0% to 100.0%.

3. NWS Algorithm Sequence:
   a. Convert ambient temperature from Celsius to Fahrenheit (T_F = T_C * 9/5 + 32).
   b. Compute the simple preliminary Steadman equation:
      HI_simple = 0.5 * (T_F + 61.0 + ((T_F - 68.0) * 1.2) + (RH * 0.094))
   c. Average HI_simple with T_F. If that average is below 80.0°F, use the average.
      Otherwise compute the full regression:
      HI = -42.379 + 2.04901523*T + 10.14333127*RH - 0.22475541*T*RH
           - 0.00683783*T^2 - 0.05481717*RH^2 + 0.00122874*T^2*RH
           + 0.00085282*T*RH^2 - 0.00000199*T^2*RH^2
   e. Apply official adjustments:
      - Low Humidity Adjustment:
        If RH < 13% and 80.0 <= T_F <= 112.0:
            adjustment = ((13 - RH) / 4) * sqrt((17 - |T_F - 95|) / 17)
            HI -= adjustment
      - High Humidity Adjustment:
        If RH > 85% and 80.0 <= T_F <= 87.0:
            adjustment = ((RH - 85) / 10) * ((87 - T_F) / 5)
            HI += adjustment
   f. Convert calculated HI from Fahrenheit back to Celsius for storage/display.
"""

import math
from decimal import Decimal, InvalidOperation

# ==============================================================================
# CONFIGURATION & CONSTANTS: EDUCATIONAL SCREENING RISK CATEGORIES
# ==============================================================================
# NOTE ON REGIONAL CRITERIA:
# These risk tiers follow generic US NOAA/NWS public screening bands.
# They DO NOT represent statutory heatwave declaration criteria of specific
# national bodies (such as the India Meteorological Department [IMD], which
# declares heatwaves based on departure from normal maximum temperatures or
# absolute thresholds of 40°C for plains / 30°C for hills).
# These screening tiers are educational and must be calibrated against local,
# legally approved meteorological and public health authority frameworks.
RISK_CATEGORIES = {
    'NORMAL': {
        'label': 'Normal',
        'badge_class': 'risk-low',
        'description': 'Minimal thermal stress. Apparent temperature matches or remains near ambient baseline.',
        'hi_max_f': 80.0,
    },
    'CAUTION': {
        'label': 'Caution',
        'badge_class': 'risk-moderate',
        'description': 'Fatigue possible with prolonged exposure and outdoor activity. Continuing activity may lead to heat cramps.',
        'hi_min_f': 80.0,
        'hi_max_f': 90.0,
    },
    'EXTREME_CAUTION': {
        'label': 'Extreme Caution',
        'badge_class': 'risk-high',
        'description': 'Heat cramps and heat exhaustion possible with prolonged exposure or physical exertion.',
        'hi_min_f': 91.0,
        'hi_max_f': 103.0,
    },
    'DANGER': {
        'label': 'Danger',
        'badge_class': 'risk-very-high',
        'description': 'Heat cramps and heat exhaustion likely; heatstroke possible with continuous outdoor exposure.',
        'hi_min_f': 104.0,
        'hi_max_f': 124.0,
    },
    'EXTREME_DANGER': {
        'label': 'Extreme Danger',
        'badge_class': 'risk-extreme',
        'description': 'Heatstroke imminent or highly likely with prolonged outdoor activity. High-risk emergency condition.',
        'hi_min_f': 125.0,
    },
}


def c_to_f(celsius):
    """Converts temperature in Celsius to Fahrenheit."""
    return (float(celsius) * 9.0 / 5.0) + 32.0


def f_to_c(fahrenheit):
    """Converts temperature in Fahrenheit to Celsius."""
    return (float(fahrenheit) - 32.0) * 5.0 / 9.0


def validate_weather_inputs(temperature_c, relative_humidity):
    """
    Validates weather inputs for physiological feasibility.
    Raises ValueError on missing, non-numeric, or out-of-range values.
    """
    if temperature_c is None or relative_humidity is None:
        raise ValueError("Temperature and relative humidity inputs cannot be None.")

    try:
        t_c = float(temperature_c)
        rh = float(relative_humidity)
    except (TypeError, ValueError, InvalidOperation) as e:
        raise ValueError(f"Invalid numeric input for temperature or relative humidity: {str(e)}")

    if math.isnan(t_c) or math.isnan(rh):
        raise ValueError("Temperature and relative humidity cannot be NaN.")

    if t_c < -50.0 or t_c > 65.0:
        raise ValueError(f"Temperature {t_c}°C is outside valid meteorological range (-50°C to 65°C).")

    if rh < 0.0 or rh > 100.0:
        raise ValueError(f"Relative humidity {rh}% is outside physically valid range (0.0% to 100.0%).")

    return t_c, rh


def map_heat_index_to_risk(heat_index_f):
    """
    Maps a calculated Heat Index in Fahrenheit to educational screening risk categories.
    """
    hi_f = float(heat_index_f)

    if hi_f < 80.0:
        cat_key = 'NORMAL'
    elif hi_f <= 90.0:
        cat_key = 'CAUTION'
    elif hi_f <= 103.0:
        cat_key = 'EXTREME_CAUTION'
    elif hi_f <= 124.0:
        cat_key = 'DANGER'
    else:
        cat_key = 'EXTREME_DANGER'

    info = RISK_CATEGORIES[cat_key]
    return {
        'category': cat_key,
        'label': info['label'],
        'badge_class': info['badge_class'],
        'description': info['description'],
        'advisory_disclaimer': (
            "Screening category based on generic NWS bands. This educational estimate does not "
            "supersede local statutory declarations (e.g. IMD heatwave criteria or official civil health alerts)."
        )
    }


def compute_nws_heat_index(temperature_c, relative_humidity):
    """
    Computes the official NWS/NOAA Heat Index apparent-temperature estimate.

    Args:
        temperature_c (float, int, Decimal): Dry-bulb air temperature in °C.
        relative_humidity (float, int, Decimal): Relative humidity percentage (0-100).

    Returns:
        dict:
            - 'heat_index_c': Decimal (rounded to 2 decimal places)
            - 'heat_index_f': Decimal (rounded to 2 decimal places)
            - 'unit': '°C'
            - 'method_used': 'simple' or 'rothfusz_regression'
            - 'adjustment_applied': 'none', 'low_humidity', or 'high_humidity'
            - 'risk': dict (category, label, badge_class, description, advisory_disclaimer)
            - 'explanation': str
            - 'is_estimated': True
    """
    t_c, rh = validate_weather_inputs(temperature_c, relative_humidity)
    t_f = c_to_f(t_c)

    # 1. Preliminary Steadman calculation
    hi_simple_f = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))

    # Average between simple estimate and ambient temperature
    avg_f = 0.5 * (hi_simple_f + t_f)

    if avg_f < 80.0:
        final_hi_f = avg_f
        method = 'simple'
        adjustment = 'none'
        explanation = (
            "Ambient conditions are below the compounding thermal stress threshold "
            "(80°F / 26.7°C). Calculated using the preliminary Steadman equation."
        )
    else:
        # 2. Full Rothfusz regression equation
        hi_rothfusz_f = (
            -42.379
            + (2.04901523 * t_f)
            + (10.14333127 * rh)
            - (0.22475541 * t_f * rh)
            - (0.00683783 * (t_f ** 2))
            - (0.05481717 * (rh ** 2))
            + (0.00122874 * (t_f ** 2) * rh)
            + (0.00085282 * t_f * (rh ** 2))
            - (0.00000199 * (t_f ** 2) * (rh ** 2))
        )
        method = 'rothfusz_regression'
        adjustment = 'none'

        # 3. Check for low-humidity adjustment
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            term1 = (13.0 - rh) / 4.0
            diff = 17.0 - abs(t_f - 95.0)
            term2 = math.sqrt(max(0.0, diff / 17.0))
            adj = term1 * term2
            hi_rothfusz_f -= adj
            adjustment = 'low_humidity'

        # 4. Check for high-humidity adjustment
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi_rothfusz_f += adj
            adjustment = 'high_humidity'

        final_hi_f = hi_rothfusz_f
        explanation = (
            f"Calculated using the 9-term NWS Rothfusz regression formula with "
            f"'{adjustment}' adjustment applied."
        )

    final_hi_c = f_to_c(final_hi_f)

    # Decimal formatting with 2 decimal places
    hi_c_dec = Decimal(str(round(final_hi_c, 2))).quantize(Decimal('0.01'))
    hi_f_dec = Decimal(str(round(final_hi_f, 2))).quantize(Decimal('0.01'))

    risk_info = map_heat_index_to_risk(final_hi_f)

    return {
        'heat_index_c': hi_c_dec,
        'heat_index_f': hi_f_dec,
        'unit': '°C',
        'method_used': method,
        'adjustment_applied': adjustment,
        'risk': risk_info,
        'explanation': explanation,
        'is_estimated': True,
    }
