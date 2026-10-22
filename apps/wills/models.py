from django.db import models
from django.contrib.auth.models import User
from apps.genealogy.models import Person
from .crypto import encrypt_with_passphrase, decrypt_with_passphrase, generate_salt


class FamilyAccount(models.Model):
    """A private login for an individual family member, created only by a
    superadmin, used to write their own will in secret and to read the
    revealed wills of their immediate relatives. Deliberately never
    is_staff — this account has no access to /admin/ or /dashboard/."""
    user                 = models.OneToOneField(User, on_delete=models.CASCADE, related_name='family_account')
    person               = models.OneToOneField(Person, on_delete=models.CASCADE, related_name='family_account')
    created_by           = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                              related_name='created_family_accounts')
    is_active            = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True,
                                                 help_text='Forces a password change on first login, since the superadmin sets the initial password.')
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Family Account'

    def __str__(self):
        return f'{self.person.full_name} ({self.user.username})'

    @property
    def immediate_relatives(self):
        """Parents, children, siblings, and spouses of this account's Person —
        the exact set who gain access once this account's will is revealed."""
        p = self.person
        relatives = list(p.siblings) + list(p.children) + list(p.spouses)
        relatives += [x for x in [p.father, p.mother] if x]
        seen, unique = set(), []
        for r in relatives:
            if r.pk not in seen:
                seen.add(r.pk)
                unique.append(r)
        return unique


class Will(models.Model):
    """A private will. Content is encrypted with a passphrase the owner
    alone chooses and never shares with the app — there is no server-held
    key that can decrypt it. Not the account holder's login password (an
    admin password reset must never be able to brick this), and not
    recoverable by a superadmin under any circumstance. The owner is
    responsible for sharing the passphrase with their family outside the
    app; losing it makes this will permanently unreadable to everyone."""
    account           = models.OneToOneField(FamilyAccount, on_delete=models.CASCADE, related_name='will')
    content_encrypted = models.BinaryField(blank=True, default=b'')
    salt              = models.BinaryField(blank=True, default=b'')
    is_revealed       = models.BooleanField(default=False)
    revealed_by       = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                           related_name='revealed_wills')
    revealed_at       = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Will'

    def __str__(self):
        status = 'revealed' if self.is_revealed else 'sealed'
        return f'Will of {self.account.person.full_name} ({status})'

    def set_content(self, plaintext, passphrase):
        """First write: mints a fresh salt. Subsequent writes reuse the
        existing salt so the same passphrase keeps working."""
        if not self.salt:
            self.salt = generate_salt()
        self.content_encrypted = encrypt_with_passphrase(plaintext, passphrase, bytes(self.salt))

    def try_decrypt(self, passphrase):
        """Returns the plaintext, or None if the passphrase is wrong."""
        if not self.content_encrypted:
            return ''
        return decrypt_with_passphrase(bytes(self.content_encrypted), passphrase, bytes(self.salt))
