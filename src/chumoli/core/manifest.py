"""
chumoli.core.manifest
=====================

Bu modul Chumoli'ning eng kritik "shartnomasi": har bir connector
(Payme, Click, 1C, yoki dlt'ning tayyor rest_api/sql_database'i)
o'zini shu formatda tanishtiradi, va dashboard/UI ANIQ shu formatdan
avtomatik forma chizadi.

NEGA BU FAYL BIRINCHI YOZILADI
--------------------------------
Bu loyihaning "yagona haqiqat manzili" (single source of truth) uchun
kontrakt. Agar bu noto'g'ri loyihalansa, har bir keyingi connector
(6 tasi qoldi: Payme, Click, 1C, Didox, Soliq, MyGov) qo'shilganda:
  - yo dashboard kodi qo'lda o'zgartiriladi (masshtablanmaydi),
  - yo har bir connector o'z-o'zidan forma chizadigan kod yozadi
    (takrorlanish, nomuvofiqlik).

Manifest orqali ikkalasi ham oldini oladi: connector faqat "menga
qanday maydonlar kerak" deb e'lon qiladi, forma chizish mantig'i
BIR MARTA, markazlashgan holda yoziladi (dashboard tomonida).

NEGA FieldSpec BUNCHALIK CHEKLANGAN (faqat bir nechta `type`)
--------------------------------------------------------------
Forma chizuvchi kod (Marimo yoki istalgan boshqa UI) faqat cheklangan
sonli input turini bilishi kerak. Agar har bir connector o'zboshimcha
"custom widget" so'rasa, dashboard kodi connector-specific if/else
zanjiriga aylanadi — bu aynan oldini olishga harakat qilayotgan narsa.
Shuning uchun FieldType enum qat'iy cheklangan: text, password, select,
number, boolean, date. Bu amalda bugungi 9 ta connector (va undan keyingi
har qanday HTTP/SQL asosidagi connector) uchun yetarli.

NEGA `secret: bool` ALOHIDA FIELD, TYPE'NING BIR QISMI EMAS
--------------------------------------------------------------
`type="password"` — bu UI'da qanday chizilishini bildiradi (nuqta bilan
yashirilgan input). `secret=True` esa SAQLASH qatlamiga signal: bu qiymat
shifrlangan holda saqlanishi SHART (qarang: chumoli.security.crypto).
Ikkalasini bitta atributga aylantirish vasvasa qiladi, lekin noto'g'ri:
masalan base_url odatda maxfiy emas, lekin ba'zan (ichki tarmoq URL)
maxfiy bo'lishi mumkin — ikki tushunchani ajratish bu holatni yechadi.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FieldType(str, Enum):
    """Forma maydonining UI ko'rinishi.

    Qat'iy ro'yxat — yangi tur qo'shish uchun bu faylni va dashboard'ning
    forma-render qismini birga o'zgartirish kerak. Bu ataylab qiyinlashtirilgan:
    connector muallifi "menga maxsus widget kerak" deganda, birinchi savol
    "bu haqiqatan yangi TUR kerakmi, yoki mavjud turlardan biri yetadimi"
    bo'lishi kerak.
    """

    TEXT = "text"
    PASSWORD = "password"
    SELECT = "select"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"


class SelectOption(BaseModel):
    """`FieldType.SELECT` uchun bitta variant."""

    value: str
    label: str


class FieldSpec(BaseModel):
    """Bitta forma maydonining to'liq ta'rifi.

    Bu klass Pydantic orqali o'zi ham validatsiya qiladi (masalan,
    SELECT turi options'siz bo'lishi mumkin emas) — shunday qilib
    noto'g'ri yozilgan manifest ishga tushish vaqtida (import bosqichida)
    aniqlanadi, forma chizilganda emas.
    """

    key: str = Field(..., description="dlt config dict'idagi kalit nomi, masalan 'merchant_id'")
    label: str = Field(..., description="Foydalanuvchiga ko'rinadigan o'zbekcha nom")
    type: FieldType = FieldType.TEXT
    required: bool = True
    secret: bool = False
    placeholder: str | None = None
    help_text: str | None = None
    default: Any = None
    options: list[SelectOption] | None = None

    @field_validator("options")
    @classmethod
    def _validate_options_present_for_select(
        cls, v: list[SelectOption] | None, info: Any
    ) -> list[SelectOption] | None:
        field_type = info.data.get("type")
        if field_type == FieldType.SELECT and not v:
            raise ValueError(
                "FieldType.SELECT uchun 'options' ro'yxati bo'sh bo'lishi mumkin emas"
            )
        return v

    @field_validator("secret")
    @classmethod
    def _password_implies_secret(cls, v: bool, info: Any) -> bool:
        # password turi deyarli har doim shifrlanishi kerak bo'lgan qiymat.
        # Buni majburlamaymiz (ba'zi holatlar uchun istisno bo'lishi mumkin),
        # lekin manifest yozuvchiga signal berish uchun eslatma qoldiramiz —
        # xato emas, chunki bu qat'iy invariant emas.
        return v


class ConnectorCategory(str, Enum):
    """Dashboard'da connectorlarni guruhlash uchun.

    UZ_PAYMENT, UZ_GOV, UZ_ERP — POSITIONING.md dagi "5 Strategic Pillars"
    bilan mos keladi (Payme/Click/Uzum = UZ_PAYMENT; Soliq/MyGov = UZ_GOV;
    Didox = UZ_GOV; 1C = UZ_ERP). UNIVERSAL — dlt'ning o'z built-in
    source'lari (rest_api, sql_database, filesystem).
    """

    UZ_PAYMENT = "uz_payment"
    UZ_GOV = "uz_gov"
    UZ_ERP = "uz_erp"
    UNIVERSAL = "universal"


class ConnectorManifest(BaseModel):
    """Bitta connectorning to'liq "pasporti".

    Bu klassning yagona vazifasi — MA'LUMOT tashish, mantiq emas.
    Haqiqiy ulanish/autentifikatsiya logikasi bu yerda YO'Q — u
    `chumoli.connectors.base.BaseUZConnector` implementatsiyasida turadi.
    Manifest faqat "qanday forma chizish kerak" va "qaysi connector
    class'ini chaqirish kerak" degan ikkita savolga javob beradi.
    """

    key: str = Field(..., description="Ichki identifikator, masalan 'payme_uz'")
    label: str = Field(..., description="Dashboard'da ko'rinadigan nom, masalan 'Payme'")
    category: ConnectorCategory
    description: str = Field(default="", description="Bir qatorlik tavsif, o'zbekcha")
    fields: list[FieldSpec] = Field(default_factory=list)
    dlt_source_factory: str = Field(
        ...,
        description=(
            "Import path — bu manifestga mos connector class'ini topish uchun. "
            "Masalan 'chumoli.connectors.rest_api.connector.RestApiConnector'. "
            "String sifatida saqlanadi (Python object emas), chunki manifest "
            "kelajakda JSON sifatida ham serializable bo'lishi kerak."
        ),
    )

    def field_by_key(self, key: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.key == key), None)

    def secret_keys(self) -> list[str]:
        """Encryption qatlami qaysi kalitlarni shifrlashi kerakligini bilish uchun.

        Bu metod atayin shu yerda — chunki "qaysi maydon maxfiy" degan
        bilim faqat manifestda yashaydi. Store qatlami (SQLite) bu haqda
        hech narsa bilmasligi kerak; u faqat "menga qaysi kalitlarni
        shifrlash kerakligini ayt" deb manifestdan so'raydi.
        """
        return [f.key for f in self.fields if f.secret]

    def validate_values(self, values: dict[str, Any]) -> list[str]:
        """Foydalanuvchi kiritgan qiymatlarni manifest talablariga solishtiradi.

        Xatolar ro'yxatini qaytaradi (bo'sh ro'yxat = valid). Bu forma
        submit qilinganda dashboard tomonidan chaqiriladi — validatsiya
        mantig'i bir joyda, connector-agnostik.
        """
        errors: list[str] = []
        for field in self.fields:
            value = values.get(field.key, field.default)
            if field.required and (value is None or value == ""):
                errors.append(f"'{field.label}' to'ldirilishi shart")
                continue
            if field.type == FieldType.SELECT and value is not None:
                valid_values = {opt.value for opt in (field.options or [])}
                if value not in valid_values:
                    errors.append(f"'{field.label}' uchun noto'g'ri qiymat")
        return errors
