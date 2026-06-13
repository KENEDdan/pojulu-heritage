from django.db import models
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

ROLE_CHOICES = [
    ('clan_admin',        'Clan Administrator'),
    ('genealogy_admin',   'Genealogy & Families Administrator'),
    ('memorial_admin',    'Memorial Records Administrator'),
    ('cultural_admin',    'Cultural Archive & Media Administrator'),
    ('elder_admin',       'Elder Interviews Administrator'),
    ('achievement_admin', 'Achievements Administrator'),
    ('content_admin',     'Full Content Administrator'),
]

ROLE_PERMISSIONS = {
    'clan_admin': [
        ('clans', 'clan'), ('clans', 'clanchief'), ('clans', 'clanevent'),
    ],
    'genealogy_admin': [
        ('genealogy', 'person'), ('genealogy', 'family'),
    ],
    'memorial_admin': [
        ('memorial', 'memorialrecord'), ('genealogy', 'person'),
    ],
    'cultural_admin': [
        ('cultural', 'culturalrecord'), ('elders', 'elderinterview'),
    ],
    'elder_admin': [
        ('elders', 'elderinterview'),
    ],
    'achievement_admin': [
        ('achievements', 'achievement'),
    ],
    'content_admin': [
        ('clans', 'clan'), ('clans', 'clanchief'), ('clans', 'clanevent'),
        ('genealogy', 'person'), ('genealogy', 'family'),
        ('memorial', 'memorialrecord'),
        ('cultural', 'culturalrecord'),
        ('elders', 'elderinterview'),
        ('achievements', 'achievement'),
        ('marriages', 'marriage'),
    ],
}

ROLE_SECTIONS = {
    'clan_admin':        ['clans'],
    'genealogy_admin':   ['genealogy', 'marriages'],
    'memorial_admin':    ['memorial'],
    'cultural_admin':    ['cultural', 'elders'],
    'elder_admin':       ['elders'],
    'achievement_admin': ['achievements'],
    'content_admin':     ['clans', 'genealogy', 'memorial', 'cultural', 'elders', 'achievements', 'marriages'],
}


class AdminProfile(models.Model):
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    role        = models.CharField(max_length=30, choices=ROLE_CHOICES)
    assigned_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_admins')
    phone       = models.CharField(max_length=50, blank=True)
    notes       = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin Profile'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    def can_access(self, section):
        if self.user.is_superuser:
            return True
        return section in ROLE_SECTIONS.get(self.role, [])

    @property
    def accessible_sections(self):
        if self.user.is_superuser:
            return list(ROLE_SECTIONS['content_admin'])
        return ROLE_SECTIONS.get(self.role, [])

    def assign_permissions(self):
        """Assign Django model permissions based on role."""
        self.user.user_permissions.clear()
        for app_label, model_name in ROLE_PERMISSIONS.get(self.role, []):
            for action in ['add', 'change', 'view', 'delete']:
                try:
                    perm = Permission.objects.get(
                        codename=f'{action}_{model_name}',
                        content_type__app_label=app_label
                    )
                    self.user.user_permissions.add(perm)
                except Permission.DoesNotExist:
                    pass