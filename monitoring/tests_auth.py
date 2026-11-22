from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import SESSION_KEY

from monitoring.models import Location, SavedLocation, WeatherRecord


class UserAuthenticationWorkflowTestCase(TestCase):
    """
    Test suite for Django session-based authentication in HeatGuard:
    - User registration success and duplicate username handling.
    - Invalid password handling.
    - Login success, session persistence, and invalid credentials failure.
    - Logout clears the authenticated session key.
    - Protected views (profile, save/remove location) redirect anonymous users to login.
    - Authenticated users can bookmark and remove saved locations.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="existing_user",
            email="existing@heatguard.local",
            password="StrongPassword#123"
        )
        self.location = Location.objects.create(
            name="Mumbai Coastal Station",
            state_or_region="Maharashtra",
            country="India",
            latitude=Decimal("18.92200"),
            longitude=Decimal("72.83470")
        )

    def test_registration_success(self):
        """Valid registration creates user with hashed password and redirects to login."""
        url = reverse('monitoring:register')
        post_data = {
            'username': 'new_observer',
            'email': 'new@heatguard.local',
            'password1': 'MySecurePass!987',
            'password2': 'MySecurePass!987',
        }
        response = self.client.post(url, data=post_data)
        self.assertRedirects(response, reverse('monitoring:login'))

        # Verify user was created in database
        self.assertTrue(User.objects.filter(username='new_observer').exists())
        user = User.objects.get(username='new_observer')
        # Verify password is hashed, not stored in plain text
        self.assertNotEqual(user.password, 'MySecurePass!987')
        self.assertTrue(user.check_password('MySecurePass!987'))

    def test_registration_duplicate_username_rejected(self):
        """Duplicate username submission is rejected with form error."""
        url = reverse('monitoring:register')
        post_data = {
            'username': 'existing_user',  # DUPLICATE
            'email': 'different@heatguard.local',
            'password1': 'AnotherPassword#456',
            'password2': 'AnotherPassword#456',
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists.")

    def test_registration_invalid_password_mismatch(self):
        """Mismatched passwords return form validation error."""
        url = reverse('monitoring:register')
        post_data = {
            'username': 'mismatch_user',
            'password1': 'PasswordOne#1',
            'password2': 'PasswordTwo#2',
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertFalse(User.objects.filter(username='mismatch_user').exists())

    def test_login_success_and_session_state(self):
        """Valid login creates session, stores user ID in session, and redirects."""
        url = reverse('monitoring:login')
        post_data = {
            'username': 'existing_user',
            'password': 'StrongPassword#123',
        }
        response = self.client.post(url, data=post_data)
        self.assertRedirects(response, reverse('monitoring:profile'))

        # Verify session contains authenticated user ID
        session = self.client.session
        self.assertEqual(session[SESSION_KEY], str(self.user.pk))

    def test_login_failure_invalid_credentials(self):
        """Invalid credentials show error message and leave session unauthenticated."""
        url = reverse('monitoring:login')
        post_data = {
            'username': 'existing_user',
            'password': 'WrongPasswordXYZ',
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 200)
        error = str(response.context['form'].non_field_errors()[0])
        self.assertIn('username and password', error)
        self.assertEqual(response.content.decode().count(error), 1)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_clears_session(self):
        """Logout flushes session and redirects to home page."""
        self.client.force_login(self.user)
        self.assertIn(SESSION_KEY, self.client.session)

        logout_url = reverse('monitoring:logout')
        response = self.client.post(logout_url)
        self.assertRedirects(response, reverse('monitoring:home'))

        # Verify session key was cleared
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_protected_profile_redirects_anonymous_user(self):
        """Anonymous user attempting to view profile is redirected to login."""
        url = reverse('monitoring:profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_authenticated_user_can_access_profile(self):
        """Authenticated user can view their profile and bookmarked stations."""
        self.client.force_login(self.user)
        url = reverse('monitoring:profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User Profile & Saved Stations")
        self.assertContains(response, "existing_user")

    def test_save_and_remove_location_workflow(self):
        """Authenticated user can bookmark and remove a station via POST."""
        self.client.force_login(self.user)

        # 1. Save location
        save_url = reverse('monitoring:save_location', kwargs={'location_id': self.location.id})
        res_save = self.client.post(save_url)
        self.assertRedirects(res_save, reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id}), fetch_redirect_response=False)
        self.assertTrue(SavedLocation.objects.filter(user=self.user, location=self.location).exists())

        # 2. Check profile reflects bookmark
        res_profile = self.client.get(reverse('monitoring:profile'))
        self.assertContains(res_profile, "Mumbai Coastal Station")

        # 3. Remove location
        remove_url = reverse('monitoring:remove_saved_location', kwargs={'location_id': self.location.id})
        res_remove = self.client.post(remove_url)
        self.assertRedirects(res_remove, reverse('monitoring:city_dashboard', kwargs={'location_id': self.location.id}), fetch_redirect_response=False)
        self.assertFalse(SavedLocation.objects.filter(user=self.user, location=self.location).exists())
