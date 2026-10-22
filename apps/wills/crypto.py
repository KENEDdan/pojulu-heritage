import os
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# There is deliberately no server-held master key anywhere in this module.
# A will's content is only ever decryptable by someone who knows the
# passphrase its owner chose — the passphrase is never stored, never
# logged, and discarded at the end of each request. This means the
# Foundation (including superadmins) cannot read a will under any
# circumstance, and a lost passphrase makes that will permanently
# unrecoverable by anyone.

PBKDF2_ITERATIONS = 600_000


def generate_salt():
    return os.urandom(16)


def _derive_key(passphrase, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode('utf-8')))


def encrypt_with_passphrase(plaintext, passphrase, salt):
    key = _derive_key(passphrase, salt)
    return Fernet(key).encrypt(plaintext.encode('utf-8'))


def decrypt_with_passphrase(token, passphrase, salt):
    """Returns the decrypted string, or None if the passphrase is wrong."""
    if not token:
        return ''
    key = _derive_key(passphrase, salt)
    try:
        return Fernet(key).decrypt(bytes(token)).decode('utf-8')
    except InvalidToken:
        return None
