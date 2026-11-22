from decimal import Decimal
from django.test import TestCase

from monitoring.heat_index import (
    compute_nws_heat_index,
    c_to_f,
    f_to_c,
    validate_weather_inputs,
    RISK_CATEGORIES,
)


class HeatIndexCalculationComprehensiveTestCase(TestCase):
    """
    Independent unit tests for the NWS/NOAA Heat Index calculation module.
    Tests conversions, equations, adjustments, boundary conditions, and risk mapping.
    """

    def test_temperature_conversion_consistency(self):
        """Verify round-trip consistency of Celsius <-> Fahrenheit conversions."""
        test_c_values = [-20.0, 0.0, 15.5, 25.0, 32.22, 40.0, 50.0]
        for c in test_c_values:
            f = c_to_f(c)
            c_back = f_to_c(f)
            self.assertAlmostEqual(c, c_back, places=4)

        # Standard physical fixed points
        self.assertAlmostEqual(c_to_f(0.0), 32.0, places=4)
        self.assertAlmostEqual(c_to_f(100.0), 212.0, places=4)
        self.assertAlmostEqual(f_to_c(32.0), 0.0, places=4)
        self.assertAlmostEqual(f_to_c(212.0), 100.0, places=4)

    def test_typical_lower_heat_conditions(self):
        """
        A preliminary average below 80°F uses the Steadman estimate and is categorized
        as NORMAL with no compounding thermal stress.
        """
        # 20°C (68°F), 50% RH
        result = compute_nws_heat_index(20.0, 50.0)
        self.assertEqual(result['method_used'], 'simple')
        self.assertEqual(result['adjustment_applied'], 'none')
        self.assertEqual(result['risk']['category'], 'NORMAL')
        self.assertEqual(result['risk']['label'], 'Normal')
        temp_f = c_to_f(20.0)
        simple_f = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (50.0 * 0.094))
        expected_f = 0.5 * (simple_f + temp_f)
        self.assertAlmostEqual(float(result['heat_index_f']), expected_f, places=2)

        # 24°C, 45% RH
        res24 = compute_nws_heat_index(24.0, 45.0)
        self.assertEqual(res24['method_used'], 'simple')
        self.assertEqual(res24['risk']['category'], 'NORMAL')

    def test_regression_threshold_uses_preliminary_average_not_ambient_temperature(self):
        """Humidity can raise the preliminary average to the regression threshold below 80°F ambient."""
        result = compute_nws_heat_index(26.2, 100.0)  # 79.16°F ambient; preliminary average > 80°F
        self.assertEqual(result['method_used'], 'rothfusz_regression')

    def test_simple_method_returns_preliminary_average_below_threshold(self):
        """Below 80°F average, use the Steadman estimate averaged with ambient temperature."""
        temperature_c = 25.0
        humidity = 100.0
        temperature_f = c_to_f(temperature_c)
        simple_f = 0.5 * (
            temperature_f + 61.0 + ((temperature_f - 68.0) * 1.2) + (humidity * 0.094)
        )
        expected_f = 0.5 * (simple_f + temperature_f)

        result = compute_nws_heat_index(temperature_c, humidity)

        self.assertEqual(result['method_used'], 'simple')
        self.assertAlmostEqual(float(result['heat_index_f']), expected_f, places=2)

    def test_high_temperature_and_high_humidity(self):
        """
        High heat and high humidity: e.g., 35°C (95°F) with 70% RH.
        Must use Rothfusz regression and evaluate to DANGER or EXTREME_DANGER.
        """
        result = compute_nws_heat_index(35.0, 70.0)
        self.assertEqual(result['method_used'], 'rothfusz_regression')
        # Heat index in Fahrenheit should be well over 115°F
        self.assertGreater(float(result['heat_index_f']), 115.0)
        # Heat index in Celsius should be > 45°C
        self.assertGreater(float(result['heat_index_c']), 45.0)
        self.assertIn(result['risk']['category'], ['DANGER', 'EXTREME_DANGER'])
        self.assertTrue(result['is_estimated'])

    def test_low_humidity_adjustment_condition(self):
        """
        Low humidity adjustment condition:
        RH < 13% and 80.0°F <= T <= 112.0°F.
        e.g., 38°C (~100.4°F) with 10% RH.
        """
        result = compute_nws_heat_index(38.0, 10.0)
        self.assertEqual(result['method_used'], 'rothfusz_regression')
        self.assertEqual(result['adjustment_applied'], 'low_humidity')
        self.assertIn('low_humidity', result['explanation'])

    def test_high_humidity_adjustment_condition(self):
        """
        High humidity adjustment condition:
        RH > 85% and 80.0°F <= T <= 87.0°F.
        80°F ≈ 26.67°C, 85°F ≈ 29.44°C, 87°F ≈ 30.56°C.
        Test with 28.5°C (~83.3°F) and 90% RH.
        """
        result = compute_nws_heat_index(28.5, 90.0)
        self.assertEqual(result['method_used'], 'rothfusz_regression')
        self.assertEqual(result['adjustment_applied'], 'high_humidity')
        self.assertIn('high_humidity', result['explanation'])
        # Heat index in Fahrenheit should be elevated above ambient
        self.assertGreater(float(result['heat_index_f']), 83.3)

    def test_risk_category_boundaries_and_explanations(self):
        """
        Confirm each risk boundary maps correctly without missing fields.
        """
        # Caution band (80 - 90 °F): e.g. 28°C (~82.4°F) with 45% RH -> HI ~ 83°F
        res_caution = compute_nws_heat_index(28.0, 45.0)
        self.assertEqual(res_caution['risk']['category'], 'CAUTION')

        # Extreme Caution (91 - 103 °F): e.g. 32°C (~89.6°F) with 55% RH -> HI ~ 97°F
        res_ext_caut = compute_nws_heat_index(32.0, 55.0)
        self.assertEqual(res_ext_caut['risk']['category'], 'EXTREME_CAUTION')

        # Danger (104 - 124 °F): e.g. 34°C (~93.2°F) with 65% RH -> HI ~ 111°F
        res_danger = compute_nws_heat_index(34.0, 65.0)
        self.assertEqual(res_danger['risk']['category'], 'DANGER')

        # Extreme Danger (>= 125 °F): e.g. 42°C (~107.6°F) with 60% RH -> HI >= 125°F
        res_ext_dang = compute_nws_heat_index(42.0, 60.0)
        self.assertEqual(res_ext_dang['risk']['category'], 'EXTREME_DANGER')
        self.assertIn("Heatstroke imminent", res_ext_dang['risk']['description'])

        # Check that educational disclaimer is present in all risk outputs
        self.assertIn("Screening category based on generic NWS bands", res_caution['risk']['advisory_disclaimer'])
        self.assertIn("IMD heatwave criteria", res_caution['risk']['advisory_disclaimer'])

    def test_invalid_and_boundary_inputs(self):
        """
        Verify validation of missing inputs, extreme values, out-of-range RH.
        """
        # None inputs
        with self.assertRaises(ValueError):
            compute_nws_heat_index(None, 50.0)

        with self.assertRaises(ValueError):
            compute_nws_heat_index(30.0, None)

        # Negative humidity
        with self.assertRaises(ValueError):
            compute_nws_heat_index(30.0, -5.0)

        # Humidity > 100%
        with self.assertRaises(ValueError):
            compute_nws_heat_index(30.0, 105.0)

        # Extreme temperature out-of-range
        with self.assertRaises(ValueError):
            compute_nws_heat_index(85.0, 50.0)

        with self.assertRaises(ValueError):
            compute_nws_heat_index(-60.0, 50.0)

        # Non-numeric string
        with self.assertRaises(ValueError):
            compute_nws_heat_index("thirty", 50.0)

    def test_decimal_and_string_inputs_handled(self):
        """Ensure Decimal and string numeric representations are handled gracefully."""
        res_dec = compute_nws_heat_index(Decimal("32.5"), Decimal("60.0"))
        res_str = compute_nws_heat_index("32.5", "60.0")
        self.assertEqual(res_dec['heat_index_c'], res_str['heat_index_c'])
        self.assertIsInstance(res_dec['heat_index_c'], Decimal)
