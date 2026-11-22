"""Shared server-side permission checks for HeatGuard staff capabilities."""


def user_can(user, permission):
    """Allow Django staff and users holding the named Django permission."""
    return user.is_authenticated and (user.is_staff or user.has_perm(permission))


def can_manage_notices(user):
    """Whether this user may access the notice management console."""
    return any(
        user_can(user, f'monitoring.{action}_officialnotice')
        for action in ('view', 'add', 'change', 'delete')
    )
