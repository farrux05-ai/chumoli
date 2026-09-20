"""
Manifest qatlami testlari.

Bu testlar ARCHITECTURE_DECISION.md 3.2 bandida aytilgan "eng kritik
qism"ni tekshiradi: manifest o'z-o'zini to'g'ri validatsiya qilishi,
va forma qiymatlarini tekshirish mantig'i connector-agnostik ishlashi.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)


def test_select_field_without_options_raises() -> None:
    """SELECT turi options'siz yaratilsa, import/validatsiya bosqichida aniqlanishi kerak.

    Nega bu muhim: agar bu tekshiruv bo'lmasa, xato faqat forma
    chizilganda (runtime'da, foydalanuvchi ko'z oldida) chiqadi.
    """
    with pytest.raises(ValidationError):
        FieldSpec(key="auth_type", label="Auth", type=FieldType.SELECT, options=None)


def test_select_field_with_options_ok() -> None:
    field = FieldSpec(
        key="auth_type",
        label="Auth",
        type=FieldType.SELECT,
        options=[SelectOption(value="none", label="Yo'q")],
    )
    assert field.options[0].value == "none"


def test_secret_keys_only_returns_marked_fields() -> None:
    """secret_keys() faqat secret=True bo'lgan maydonlarni qaytarishi kerak.

    Bu — ControlStore.save() ning qaysi qiymatlarni shifrlashini
    belgilaydigan yagona manba, shuning uchun bu test to'g'ridan-to'g'ri
    xavfsizlik invariantini tekshiradi.
    """
    manifest = ConnectorManifest(
        key="test_connector",
        label="Test",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="dummy.path",
        fields=[
            FieldSpec(key="base_url", label="URL", secret=False),
            FieldSpec(key="api_key", label="Key", type=FieldType.PASSWORD, secret=True),
            FieldSpec(key="username", label="User", secret=False),
        ],
    )
    assert manifest.secret_keys() == ["api_key"]


def test_validate_values_flags_missing_required_field() -> None:
    manifest = ConnectorManifest(
        key="test_connector",
        label="Test",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="dummy.path",
        fields=[FieldSpec(key="base_url", label="Base URL", required=True)],
    )
    errors = manifest.validate_values({})
    assert len(errors) == 1
    assert "Base URL" in errors[0]


def test_validate_values_flags_invalid_select_option() -> None:
    manifest = ConnectorManifest(
        key="test_connector",
        label="Test",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="dummy.path",
        fields=[
            FieldSpec(
                key="auth_type",
                label="Auth",
                type=FieldType.SELECT,
                options=[SelectOption(value="none", label="Yo'q")],
            )
        ],
    )
    errors = manifest.validate_values({"auth_type": "not_a_real_option"})
    assert len(errors) == 1


def test_validate_values_passes_for_correct_input() -> None:
    manifest = ConnectorManifest(
        key="test_connector",
        label="Test",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="dummy.path",
        fields=[FieldSpec(key="base_url", label="Base URL", required=True)],
    )
    errors = manifest.validate_values({"base_url": "https://example.com"})
    assert errors == []
