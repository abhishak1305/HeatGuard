import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from monitoring.models import OfficialNotice


class Command(BaseCommand):
    help = "Sets up default HeatGuard role groups, permissions, and demo user accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Reset existing demo account passwords from the corresponding environment variables.',
        )

    def handle(self, *args, **options):
        # 1. Weather Authority Staff Group
        staff_group, created = Group.objects.get_or_create(name='Weather Authority Staff')

        # Assign permissions on OfficialNotice
        notice_ct = ContentType.objects.get_for_model(OfficialNotice)
        notice_perms = Permission.objects.filter(
            content_type=notice_ct,
            codename__in=[
                'add_officialnotice',
                'change_officialnotice',
                'delete_officialnotice',
                'view_officialnotice',
            ]
        )
        staff_group.permissions.add(*notice_perms)

        status = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{status} group '{staff_group.name}' with {notice_perms.count()} permissions."
            )
        )

        # 2. Demo registered user
        demo_password = os.environ.get('HEATGUARD_DEMO_USER_PASSWORD')
        staff_password = os.environ.get('HEATGUARD_STAFF_USER_PASSWORD')
        if options['force'] and (not demo_password or not staff_password):
            raise CommandError('--force requires both HEATGUARD_DEMO_USER_PASSWORD and HEATGUARD_STAFF_USER_PASSWORD.')

        demo_user, u_created = User.objects.get_or_create(username='demouser')
        if u_created:
            demo_user.set_password(demo_password) if demo_password else demo_user.set_unusable_password()
            demo_user.save(update_fields=['password'])
        elif options['force']:
            demo_user.set_password(demo_password)
            demo_user.save(update_fields=['password'])
        if u_created and not demo_password:
            demo_message = "Created demo user 'demouser' with no usable password; set one with `manage.py changepassword demouser`."
        elif u_created or options['force']:
            demo_message = "Created or updated demo user 'demouser' with the configured password."
        else:
            demo_message = "Already exists demo user 'demouser'; its existing password was left unchanged."
        self.stdout.write(self.style.SUCCESS(demo_message))

        # 3. Staff authority user
        staff_user, s_created = User.objects.get_or_create(
            username='staffuser',
            defaults={'is_staff': True, 'is_superuser': False},
        )
        if s_created:
            staff_user.set_password(staff_password) if staff_password else staff_user.set_unusable_password()
            staff_user.save(update_fields=['password'])
        elif options['force']:
            staff_user.set_password(staff_password)
            staff_user.save(update_fields=['password'])
        staff_user.groups.add(staff_group)
        if s_created and not staff_password:
            staff_message = "Created staff user 'staffuser' with no usable password; set one with `manage.py changepassword staffuser`."
        elif s_created or options['force']:
            staff_message = "Created or updated staff user 'staffuser' with the configured password."
        else:
            staff_message = "Already exists staff user 'staffuser'; its existing password was left unchanged."
        self.stdout.write(self.style.SUCCESS(staff_message))
