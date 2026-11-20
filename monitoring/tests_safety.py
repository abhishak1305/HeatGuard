from django.test import TestCase, Client
from django.urls import reverse

from monitoring.safety_guidance import (
    CATEGORY_SAFETY_GUIDANCE,
    GROUP_SAFETY_GUIDANCE,
    OFFICIAL_HEALTH_RESOURCES,
    get_safety_guidance_for_risk,
)


class SafetyGuidanceTestCase(TestCase):
    """
    Tests for the Safety Guidance module and public health pages:
    - Each risk category returns clear, non-diagnostic guidance.
    - Missing/unknown risk does not display falsely reassuring messages.
    - Safety guidance page renders properly with links to official health authorities.
    """

    def setUp(self):
        self.client = Client()

    def test_each_risk_category_displays_intended_guidance(self):
        """Confirm distinct, appropriate advice for each standard screening category."""
        categories = ['NORMAL', 'CAUTION', 'EXTREME_CAUTION', 'DANGER', 'EXTREME_DANGER']
        for cat in categories:
            guidance = get_safety_guidance_for_risk(cat)
            self.assertIn('hydration', guidance)
            self.assertIn('shade_and_rest', guidance)
            self.assertIn('outdoor_activity', guidance)
            self.assertIn('vulnerable_care', guidance)
            self.assertIn('warning_signs', guidance)
            # Ensure hydration mentions fluids or water
            self.assertTrue('water' in guidance['hydration'].lower() or 'fluid' in guidance['hydration'].lower())

    def test_missing_or_unknown_risk_does_not_reassure_falsely(self):
        """Missing or unknown risk category returns cautious fallback without falsely reassuring message."""
        unknown_guidance = get_safety_guidance_for_risk('UNKNOWN_CODE')
        self.assertEqual(unknown_guidance['urgency_level'], 'unknown')
        self.assertIn("could not be evaluated", unknown_guidance['summary'])
        # Must not state conditions are safe or normal
        self.assertNotIn("minimal thermal heat stress", unknown_guidance['summary'].lower())

        none_guidance = get_safety_guidance_for_risk(None)
        self.assertEqual(none_guidance['urgency_level'], 'unknown')

    def test_public_safety_page_renders_with_official_resources(self):
        """Public safety page renders all categories, high-risk groups, and official health links."""
        url = reverse('monitoring:safety_guidance')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public Heat Safety")
        self.assertContains(response, "Thermal Health Guidance")
        self.assertContains(response, "Emergency Medical Notice")
        self.assertContains(response, "Critical Warning Signs")
        self.assertContains(response, "CALL LOCAL EMERGENCY SERVICES")
        # Check vulnerable group titles
        self.assertContains(response, "Outdoor Workers &amp; Laborers")
        self.assertContains(response, "Older Adults (Seniors)")
        self.assertContains(response, "Infants &amp; Young Children")
        # Check reliable official public health resources
        self.assertContains(response, "World Health Organization")
        self.assertContains(response, "National Disaster Management Authority")
        self.assertContains(response, "Centers for Disease Control and Prevention")
        self.assertContains(response, "India Meteorological Department")
