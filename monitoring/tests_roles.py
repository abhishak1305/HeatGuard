from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command

from monitoring.models import Location, WeatherRecord, OfficialNotice, SavedLocation


class RoleAndSessionWorkflowTestCase(TestCase):
    """
    Automated test suite verifying:
    1. Users cannot access or remove another user's saved locations.
    2. Anonymous users cannot access private history or profile.
    3. Non-staff users cannot create or edit official notices.
    4. Staff permissions and groups work as expected.
    5. Session history behaves correctly and does not contain sensitive data.
    6. Non-sensitive preferences (like temperature unit cookie) work cleanly.
    """

    def setUp(self):
        self.client = Client()

        # Create two test users
        self.user1 = User.objects.create_user(
            username="user_one",
            email="user1@heatguard.local",
            password="Password123!"
        )
        self.user2 = User.objects.create_user(
            username="user_two",
            email="user2@heatguard.local",
            password="Password123!"
        )

        # Create a Weather Authority Staff group with permissions
        self.staff_group = Group.objects.create(name="Weather Authority Staff")
        notice_ct = ContentType.objects.get_for_model(OfficialNotice)
        perms = Permission.objects.filter(
            content_type=notice_ct,
            codename__in=['add_officialnotice', 'change_officialnotice', 'view_officialnotice']
        )
        self.staff_group.permissions.set(perms)

        # Create a group-assigned staff user (not superuser, not is_staff=True, but has group permissions)
        self.authority_user = User.objects.create_user(
            username="authority_officer",
            email="officer@heatguard.local",
            password="Password123!"
        )
        self.authority_user.groups.add(self.staff_group)

        # Create a standard Django is_staff user
        self.django_staff = User.objects.create_user(
            username="django_staff_user",
            email="staff@heatguard.local",
            password="Password123!",
            is_staff=True
        )

        # Create test locations
        self.station1 = Location.objects.create(
            name="Delhi Station",
            state_or_region="Delhi",
            country="India",
            latitude=Decimal("28.61390"),
            longitude=Decimal("77.20900")
        )
        self.station2 = Location.objects.create(
            name="Mumbai Coastal",
            state_or_region="Maharashtra",
            country="India",
            latitude=Decimal("18.92200"),
            longitude=Decimal("72.83470")
        )

    def test_setup_roles_does_not_reset_existing_demo_account_passwords(self):
        """Rerunning setup_roles must not replace credentials on existing users."""
        demo_user = User.objects.create_user('demouser', password='ExistingSafePassword!')
        staff_user = User.objects.create_user(
            'staffuser', password='ExistingStaffPassword!', is_staff=False
        )

        output = StringIO()
        call_command('setup_roles', stdout=output)

        demo_user.refresh_from_db()
        staff_user.refresh_from_db()
        self.assertTrue(demo_user.check_password('ExistingSafePassword!'))
        self.assertTrue(staff_user.check_password('ExistingStaffPassword!'))
        self.assertFalse(staff_user.is_staff)
        self.assertIn('Weather Authority Staff', staff_user.groups.values_list('name', flat=True))
        self.assertNotIn('HeatGuard#2026!', output.getvalue())
        self.assertIn('existing password was left unchanged', output.getvalue())

    def test_setup_roles_creates_demo_accounts_with_unusable_passwords(self):
        """New bootstrap accounts require an explicit password set by an operator."""
        output = StringIO()
        call_command('setup_roles', stdout=output)

        demo_user = User.objects.get(username='demouser')
        staff_user = User.objects.get(username='staffuser')
        self.assertFalse(demo_user.has_usable_password())
        self.assertFalse(staff_user.has_usable_password())
        self.assertTrue(staff_user.is_staff)
        self.assertNotIn('HeatGuard#2026!', output.getvalue())
        self.assertIn('no usable password', output.getvalue())

    @patch.dict('os.environ', {
        'HEATGUARD_DEMO_USER_PASSWORD': 'NewDemoPass-7842',
        'HEATGUARD_STAFF_USER_PASSWORD': 'NewStaffPass-6391',
    })
    def test_setup_roles_force_resets_only_when_explicitly_requested(self):
        demo = User.objects.create_user('demouser', password='OldDemoPass-7842')
        staff = User.objects.create_user('staffuser', password='OldStaffPass-6391', is_staff=True)
        self.staff_group.permissions.add(Permission.objects.get(codename='add_user'))

        call_command('setup_roles')
        demo.refresh_from_db()
        self.assertTrue(demo.check_password('OldDemoPass-7842'))

        output = StringIO()
        call_command('setup_roles', '--force', stdout=output)
        demo.refresh_from_db()
        staff.refresh_from_db()
        self.assertTrue(demo.check_password('NewDemoPass-7842'))
        self.assertTrue(staff.check_password('NewStaffPass-6391'))
        self.assertTrue(self.staff_group.permissions.filter(codename='add_user').exists())
        self.assertNotIn('NewDemoPass-7842', output.getvalue())
        self.assertIn('with the configured password', output.getvalue())

    def test_anonymous_cannot_access_profile_or_history(self):
        """Anonymous public visitor cannot access private profile or query history."""
        url = reverse('monitoring:profile')
        response = self.client.get(url)
        # Should redirect to login page with next parameter
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('monitoring:login'), response.url)
        self.assertIn('next=', response.url)

    def test_users_cannot_access_or_remove_other_users_saved_locations(self):
        """A user cannot delete another user's saved locations."""
        # user1 saves station1
        SavedLocation.objects.create(user=self.user1, location=self.station1)
        self.assertEqual(SavedLocation.objects.filter(user=self.user1).count(), 1)

        # user2 logs in
        self.client.login(username="user_two", password="Password123!")
        
        # user2 checks their profile -> station1 should NOT appear
        profile_resp = self.client.get(reverse('monitoring:profile'))
        self.assertEqual(profile_resp.status_code, 200)
        self.assertNotContains(profile_resp, "Delhi Station")

        # user2 attempts to remove user1's saved station
        remove_url = reverse('monitoring:remove_saved_location', kwargs={'location_id': self.station1.id})
        remove_resp = self.client.post(remove_url)
        self.assertEqual(remove_resp.status_code, 302)

        # Verify user1's bookmark is untouched!
        self.assertEqual(SavedLocation.objects.filter(user=self.user1, location=self.station1).count(), 1)
        self.assertEqual(SavedLocation.objects.filter(user=self.user2).count(), 0)

    def test_non_staff_users_cannot_create_or_edit_official_notices(self):
        """Regular registered user is forbidden (403) from creating or editing notices."""
        self.client.login(username="user_one", password="Password123!")

        create_url = reverse('monitoring:notice_create')
        post_data = {
            'location': self.station1.id,
            'title': 'Unauthorized Notice Attempt',
            'severity': 'WARNING',
            'issuing_organization': 'Fake Agency',
            'source_url': 'https://example.com/unauthorized',
            'valid_from': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'valid_until': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'),
            'message': 'This should fail.',
            'is_published': True,
        }
        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(OfficialNotice.objects.count(), 0)

        # Also cannot access staff dashboard
        staff_dash_resp = self.client.get(reverse('monitoring:staff_dashboard'))
        self.assertEqual(staff_dash_resp.status_code, 403)

    def test_staff_via_django_group_permissions_can_publish_notice(self):
        """User possessing the 'Weather Authority Staff' group permissions can create official notices."""
        self.client.login(username="authority_officer", password="Password123!")

        create_url = reverse('monitoring:notice_create')
        get_resp = self.client.get(create_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, "Publish New Official Notice")

        now = timezone.now()
        post_data = {
            'location': self.station1.id,
            'title': 'High Heat Advisory for Delhi',
            'severity': 'ADVISORY',
            'issuing_organization': 'India Meteorological Department (IMD)',
            'source_url': 'https://mausam.imd.gov.in/delhi',
            'issued_at': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_from': now.strftime('%Y-%m-%dT%H:%M'),
            'valid_until': (now + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
            'message': 'Daytime heat index expected to exceed 41C. Take precautions.',
            'is_published': True,
        }
        post_resp = self.client.post(create_url, post_data)
        self.assertRedirects(post_resp, reverse('monitoring:notice_list'))

        notice = OfficialNotice.objects.get(title='High Heat Advisory for Delhi')
        self.assertEqual(notice.created_by, self.authority_user)
        self.assertEqual(notice.issuing_organization, 'India Meteorological Department (IMD)')

        # Staff console access should also succeed
        dash_resp = self.client.get(reverse('monitoring:staff_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "High Heat Advisory for Delhi")

    def test_change_permission_alone_allows_notice_management_dashboard(self):
        """Users allowed to edit notices can reach the list containing edit links."""
        self.authority_user.user_permissions.add(
            Permission.objects.get(content_type__app_label='monitoring', codename='change_officialnotice')
        )
        self.client.force_login(self.authority_user)

        response = self.client.get(reverse('monitoring:staff_dashboard'))

        self.assertEqual(response.status_code, 200)

    def test_session_history_records_non_sensitive_data_only(self):
        """
        Verify that searching stores non-sensitive location info (id, name, country) in the session
        and never stores credentials, passwords, or personal secrets.
        """
        # Anonymous visitor searches for station1
        search_url = reverse('monitoring:city_search') + f'?city={self.station1.name}'
        response = self.client.get(search_url)
        self.assertRedirects(response, reverse('monitoring:city_dashboard', kwargs={'location_id': self.station1.id}), fetch_redirect_response=False)

        session = self.client.session
        self.assertIn('recent_searches', session)
        recent_searches = session['recent_searches']
        self.assertEqual(len(recent_searches), 1)
        self.assertEqual(recent_searches[0]['name'], self.station1.name)
        self.assertEqual(recent_searches[0]['id'], self.station1.id)

        # Inspect session keys: Ensure no password, token, or secret is ever saved
        for key, value in session.items():
            self.assertNotIn('password', key.lower())
            self.assertNotIn('secret', key.lower())
            if isinstance(value, dict):
                self.assertNotIn('password', str(value).lower())

        # When visiting search page again, recent session searches are rendered
        search_page_resp = self.client.get(reverse('monitoring:city_search'))
        self.assertEqual(search_page_resp.status_code, 200)
        self.assertContains(search_page_resp, "Recent Searches (Session History):")
        self.assertContains(search_page_resp, self.station1.name)

    def test_temperature_unit_preference_cookie(self):
        """User can toggle temperature unit cookie safely without sensitive data exposure."""
        pref_url = reverse('monitoring:set_temperature_unit') + '?unit=F'
        response = self.client.get(pref_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('heatguard_temp_unit', response.cookies)
        self.assertEqual(response.cookies['heatguard_temp_unit'].value, 'F')

    def test_temperature_preference_rejects_external_referer(self):
        """An external Referer cannot redirect users away from HeatGuard."""
        url = reverse('monitoring:set_temperature_unit') + '?unit=F'

        response = self.client.get(url, HTTP_REFERER='https://attacker.example/phishing')

        self.assertRedirects(response, reverse('monitoring:home'))
