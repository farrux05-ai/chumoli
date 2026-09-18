"""
Encryption (Fernet) qatlami testlari.

Bu testlar uzpipe.security.crypto.CredentialCipher ning asosiy
invariantini tekshiradi: encrypt/decrypt round-trip ishonchli
ishlashi, va noto'g'ri key bilan deshifrlash aniq xato berishi
(InvalidToken) — ARCHITECTURE_DECISION.md 3.3 bandidagi talab.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken

from uzpipe.security.crypto import CredentialCipher


def test_encrypt_decrypt_round_trip(tmp_path) -> None:
    cipher = CredentialCipher(key_path=tmp_path / "key")
    plaintext = "sk_live_super_secret_12345"
    encrypted = cipher.encrypt(plaintext)

    assert encrypted != plaintext
    assert cipher.decrypt(encrypted) == plaintext


def test_key_file_created_with_restricted_permissions(tmp_path) -> None:
    key_path = tmp_path / "master.key"
    CredentialCipher(key_path=key_path)

    assert key_path.exists()
    mode = key_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_key_is_reused_across_instances(tmp_path) -> None:
    """Ikkinchi marta CredentialCipher yaratilganda YANGI key yaratilmasligi kerak.

    Aks holda avval shifrlangan barcha ma'lumot o'qib bo'lmas holga
    kelardi — bu MVP uchun jiddiy regressiya bo'lardi.
    """
    key_path = tmp_path / "master.key"
    cipher_1 = CredentialCipher(key_path=key_path)
    encrypted = cipher_1.encrypt("qiymat")

    cipher_2 = CredentialCipher(key_path=key_path)
    assert cipher_2.decrypt(encrypted) == "qiymat"


def test_decrypt_with_wrong_key_raises_invalid_token(tmp_path) -> None:
    cipher_a = CredentialCipher(key_path=tmp_path / "key_a")
    cipher_b = CredentialCipher(key_path=tmp_path / "key_b")

    encrypted = cipher_a.encrypt("maxfiy")
    with pytest.raises(InvalidToken):
        cipher_b.decrypt(encrypted)


def test_encrypt_dict_and_decrypt_dict(tmp_path) -> None:
    cipher = CredentialCipher(key_path=tmp_path / "key")
    values = {"merchant_id": "abc123", "api_key": "sk_test_xyz"}

    encrypted = cipher.encrypt_dict(values)
    assert all(v != values[k] for k, v in encrypted.items())

    decrypted = cipher.decrypt_dict(encrypted)
    assert decrypted == values
