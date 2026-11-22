import os
import subprocess
import sys

from django.test import SimpleTestCase


class DeploymentSettingsTests(SimpleTestCase):
    def run_settings_probe(self, overrides):
        env = os.environ.copy()
        for name in (
            'DJANGO_DEBUG', 'DJANGO_SECRET_KEY', 'DJANGO_ALLOWED_HOSTS',
            'DJANGO_SECURE_SSL_REDIRECT', 'DJANGO_SECURE_HSTS_SECONDS',
            'DJANGO_SESSION_COOKIE_SECURE', 'DJANGO_CSRF_COOKIE_SECURE',
        ):
            env.pop(name, None)
        env['DJANGO_SETTINGS_MODULE'] = 'heatguard_project.settings'
        env.update(overrides)
        return subprocess.run(
            [sys.executable, '-c', (
                'from django.conf import settings; '
                'print("|".join(str(value) for value in ('
                'settings.DEBUG, settings.SECURE_SSL_REDIRECT, '
                'settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE)))'
            )],
            capture_output=True, text=True, env=env, check=False,
        )

    def test_omitted_debug_defaults_to_secure_production_settings(self):
        result = self.run_settings_probe({
            'DJANGO_SECRET_KEY': 'audit-test-key-that-is-not-used-for-signing-anything',
            'DJANGO_ALLOWED_HOSTS': 'example.test',
        })

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('False|True|True|True', result.stdout)

    def test_missing_production_secret_fails_startup(self):
        result = self.run_settings_probe({'DJANGO_ALLOWED_HOSTS': 'example.test'})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY must be set', result.stderr)

    def test_missing_production_hosts_fails_startup(self):
        result = self.run_settings_probe({
            'DJANGO_SECRET_KEY': 'audit-test-key-that-is-not-used-for-signing-anything',
        })

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_ALLOWED_HOSTS must list the production host names', result.stderr)

    def test_explicit_local_debug_allows_temporary_key(self):
        result = self.run_settings_probe({'DJANGO_DEBUG': '1'})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('True|False|False|False', result.stdout)
