from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from monitoring.models import Location, OfficialNotice


class OfficialNoticeStaffWorkflowTestCase(TestCase):
    """
    Test suite for Official Notice security, workflows, and public rendering:
    - Anonymous user cannot access create view (redirected to login).
    - Authenticated non-staff user receives 403 Forbidden.
    - Staff user can create notice with POST-redirect-GET and edit existing notice.
    - Rejection of invalid validity dates (valid_until <= valid_from).
    - Unpublished notices are never shown publicly.
    - Expired notices are separated and not displayed as active.
    """

    def setUp(self):
        self.client = Client()
        self.location = Location.objects.create(
            name="New Delhi Regional Center",
            state_or_region="Delhi",
            country="India",
            latitude=Decimal("28.61390"),
            longitude=Decimal("77.20900")
        )
        # Normal registered user (non-staff)
        self.regular_user = User.objects.create_user(
            username="citizen_ram",
            email="ram@example.com",
            password="userpass123"
        )
        # Staff user
        self.staff_user = User.objects.create_user(
            username="officer_meera",
            email="meera@imd.gov.in",
            password="staffpass123",
            is_staff=True
        )

    def test_anonymous_user_cannot_create_notice(self):
        """Anonymous user trying to access notice_create is redirected to login."""
        url = reverse('monitoring:notice_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_normal_user_cannot_create_notice_forbidden(self):
        """Authenticated non-staff user receives 403 Forbidden."""
        self.client.force_login(self.regular_user)
        url = reverse('monitoring:notice_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_access_notice_create_get(self):
        """Authorized staff can access the notice creation form."""
        self.client.force_login(self.staff_user)
        url = reverse('monitoring:notice_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publish New Official Notice")
        self.assertContains(response, 'Issued At (IST, Asia/Kolkata)')
        self.assertContains(response, 'HeatGuard validates URL format only')

    def test_staff_user_can_create_notice_post_redirect_get(self):
        """Staff user can create notice via POST and is redirected via PRG pattern."""
        self.client.force_login(self.staff_user)
        url = reverse('monitoring:notice_create')
        now = timezone.localtime(timezone.now())
        post_data = {
            'location': self.location.id,
            'title': 'Red Level Heatwave Emergency Directive',
            'severity': 'EMERGENCY',
            'issuing_organization': 'India Meteorological Department (IMD)',
            'source_url': 'https://mausam.imd.gov.in/heatwave-alert-101',
            'issued_at': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_from': (now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'valid_until': (now + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'message': 'Severe heatwave conditions over Delhi NCR. Avoid outdoor activity from 11:00 to 16:00.',
            'is_published': 'on',
        }
        response = self.client.post(url, data=post_data)
        self.assertRedirects(response, reverse('monitoring:notice_list'))

        # Verify notice in database
        notice = OfficialNotice.objects.get(title='Red Level Heatwave Emergency Directive')
        self.assertEqual(notice.created_by, self.staff_user)
        self.assertEqual(notice.severity, 'EMERGENCY')
        self.assertEqual(notice.status, 'active')
        self.assertLessEqual(notice.issued_at, notice.valid_until)
        expected_valid_from = datetime.strptime(
            post_data['valid_from'], '%Y-%m-%dT%H:%M'
        ).replace(tzinfo=ZoneInfo('Asia/Kolkata'))
        self.assertEqual(notice.valid_from, expected_valid_from)

    def test_notice_datetime_local_values_expire_in_ist(self):
        """A datetime-local expiry is interpreted as Asia/Kolkata wall time."""
        self.client.force_login(self.staff_user)
        post_data = {
            'location': self.location.pk,
            'title': 'IST Expiry Test',
            'severity': 'WARNING',
            'issuing_organization': 'IMD',
            'source_url': 'https://mausam.imd.gov.in/ist-expiry',
            'issued_at': '2026-11-20T09:00',
            'valid_from': '2026-11-20T10:00',
            'valid_until': '2026-11-20T11:00',
            'message': 'Test expiry time interpretation.',
            'is_published': 'on',
        }

        response = self.client.post(reverse('monitoring:notice_create'), data=post_data)

        self.assertRedirects(response, reverse('monitoring:notice_list'))
        notice = OfficialNotice.objects.get(title='IST Expiry Test')
        self.assertEqual(
            notice.valid_until,
            datetime(2026, 11, 20, 11, 0, tzinfo=ZoneInfo('Asia/Kolkata')),
        )
        self.assertEqual(notice.status, 'expired')

    def test_staff_user_can_edit_notice(self):
        """Staff user can edit an existing official notice."""
        self.client.force_login(self.staff_user)
        now = timezone.now()
        notice = OfficialNotice.objects.create(
            location=self.location,
            title="Initial Title",
            severity="ADVISORY",
            issuing_organization="IMD",
            source_url="https://mausam.imd.gov.in/bulletin",
            valid_from=now,
            valid_until=now + timedelta(days=1),
            message="Initial advisory text.",
            created_by=self.staff_user,
            is_published=True
        )

        edit_url = reverse('monitoring:notice_edit', kwargs={'notice_id': notice.id})
        edit_data = {
            'location': self.location.id,
            'title': 'Updated Title: Severe Advisory',
            'severity': 'WARNING',
            'issuing_organization': 'IMD',
            'source_url': 'https://mausam.imd.gov.in/bulletin-updated',
            'issued_at': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_from': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_until': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'message': 'Updated advisory directives.',
            'is_published': 'on',
        }
        response = self.client.post(edit_url, data=edit_data)
        self.assertRedirects(response, reverse('monitoring:notice_list'))

        notice.refresh_from_db()
        self.assertEqual(notice.title, 'Updated Title: Severe Advisory')
        self.assertEqual(notice.severity, 'WARNING')

    def test_invalid_validity_dates_rejected_in_form(self):
        """Form rejects valid_until <= valid_from."""
        self.client.force_login(self.staff_user)
        url = reverse('monitoring:notice_create')
        now = timezone.now()
        post_data = {
            'location': self.location.id,
            'title': 'Faulty Dates Notice',
            'severity': 'WARNING',
            'issuing_organization': 'IMD',
            'source_url': 'https://mausam.imd.gov.in/test',
            'issued_at': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_from': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_until': (now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),  # INVALID
            'message': 'Test message.',
            'is_published': 'on',
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "strictly later than &#x27;valid_from&#x27;")
        self.assertFalse(OfficialNotice.objects.filter(title='Faulty Dates Notice').exists())

    def test_unpublished_notice_not_shown_publicly(self):
        """Draft or unpublished notices are excluded from the public notice list and city dashboard."""
        now = timezone.now()
        OfficialNotice.objects.create(
            location=self.location,
            title="Draft Internal Bulletin",
            severity="ADVISORY",
            issuing_organization="IMD",
            source_url="https://mausam.imd.gov.in/draft",
            valid_from=now,
            valid_until=now + timedelta(days=1),
            message="Internal notes not for public dissemination.",
            created_by=self.staff_user,
            is_published=False  # UNPUBLISHED
        )

        response = self.client.get(reverse('monitoring:notice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Draft Internal Bulletin")

    def test_expired_notices_separated_from_active(self):
        """Expired notices appear under the expired archive, not active notices."""
        now = timezone.now()
        expired_notice = OfficialNotice.objects.create(
            location=self.location,
            title="Expired Heat Watch from Last Week",
            severity="WATCH",
            issuing_organization="IMD",
            source_url="https://mausam.imd.gov.in/archive-1",
            valid_from=now - timedelta(days=5),
            valid_until=now - timedelta(days=2),
            message="Historic watch that has elapsed.",
            created_by=self.staff_user,
            is_published=True
        )

        response = self.client.get(reverse('monitoring:notice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expired Notices Archive")
        self.assertContains(response, "Expired Heat Watch from Last Week")
        self.assertEqual(expired_notice.status, 'expired')

    def test_notice_creator_cannot_be_deleted_while_notice_exists(self):
        now = timezone.now()
        notice = OfficialNotice.objects.create(
            location=self.location,
            title='Protected record',
            message='Published notice retained for audit.',
            severity='WARNING',
            issuing_organization='IMD',
            source_url='https://mausam.imd.gov.in/protected',
            valid_from=now,
            valid_until=now + timedelta(hours=2),
            created_by=self.staff_user,
        )
        with self.assertRaises(ProtectedError):
            self.staff_user.delete()
        self.assertTrue(OfficialNotice.objects.filter(pk=notice.pk).exists())
