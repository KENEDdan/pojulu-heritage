from django import forms


class SetWillForm(forms.Form):
    """First-time write: the owner chooses a Will Passphrase — separate
    from their login password so an admin password reset can never lock
    them out of their own will."""
    passphrase = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Choose a Will Passphrase (min. 12 characters)'}))
    confirm_passphrase = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Confirm passphrase'}))
    content = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control', 'rows': 16, 'placeholder': 'Write your will here…'}))

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('passphrase'), cleaned.get('confirm_passphrase')
        if p1 and len(p1) < 12:
            raise forms.ValidationError(
                'Your Will Passphrase must be at least 12 characters — this protects data '
                'that no one, including Foundation staff, can otherwise recover.')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passphrases do not match.')
        return cleaned


class UpdateWillForm(forms.Form):
    """Re-writing an existing will: only the existing passphrase is
    accepted, verified against the stored ciphertext before anything is
    overwritten, so a typo can't silently invalidate a passphrase already
    shared with family."""
    passphrase = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Enter your existing Will Passphrase'}))
    content = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'form-control', 'rows': 16, 'placeholder': 'Write your will here…'}))


class PassphrasePromptForm(forms.Form):
    passphrase = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Enter the Will Passphrase'}))


class ChangeLoginPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}))

    def clean_new_password(self):
        pw = self.cleaned_data['new_password']
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(pw)
        except DjangoValidationError as e:
            raise forms.ValidationError(e.messages)
        return pw

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') and cleaned.get('confirm_password') and cleaned['new_password'] != cleaned['confirm_password']:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned
