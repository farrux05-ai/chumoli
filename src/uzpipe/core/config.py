"""
uzpipe.core.config
====================

PipelineConfig — pipeline konfiguratsiyasining yagona haqiqat manzili.

NEGA BU MODEL YAML'DAN CHIQARILDI
------------------------------------
Avvalgi UzPipe versiyasida pipeline.yml fayli o'qilib, shu klassga
o'xshash struktura hosil qilinardi. Foydalanuvchi hech qanday kod
yoki YAML yozmasligi kerak degan talabdan so'ng, YAML endi
KIRISH FORMATI EMAS.

Ammo diqqat: bu klassning o'zi deyarli o'zgarmadi. Bu ataylab shunday —
buning isboti: `PipelineConfig.model_validate(d)` ORQALI istalgan
manbadan (dict, JSON, SQLite'dan o'qilgan qator, kelajakda hatto
YAML'dan ham agar kimdir shuni xohlasa) yaratish mumkin. Demak,
"YAML yo'q" degani — bu MODEL darajasidagi cheklov emas, balki
UI/CLI qatlamida "foydalanuvchidan hech qachon xom YAML matni
so'ralmaydi" degan siyosat. Model o'zi format-agnostik qolishi kerak,
aks holda ertaga boshqa kirish usuli (masalan REST API orqali JSON)
kerak bo'lganda yana bir marta qayta yozishga to'g'ri keladi.

NEGA BU YERDA dlt'GA CHAQIRUV YO'Q
--------------------------------------
Bu fayl dlt haqida HECH NARSA bilmaydi (import qilmaydi ham). Sabab —
"config" va "dlt'ga qanday o'tkazish" ikkita alohida mas'uliyat.
PipelineConfig — sof ma'lumot strukturasi, validatsiya bilan.
dlt.pipeline() ni chaqiruvchi kod `uzpipe.core.pipeline_runner` da
turadi. Bu ajratish shuni anglatadi: agar ertaga dlt'ning API'si
o'zgarsa (masalan V2 chiqsa), faqat runner o'zgaradi — bu fayl
tegilmaydi. Va aksincha: agar config formatiga yangi maydon
qo'shilsa, dlt chaqiruv kodi bilmasdan ham kod compile bo'ladi,
lekin runner'da ishlatilmagan maydon aniq ko'rinadi.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class WriteDisposition(str, Enum):
    """dlt'ning o'zidagi write_disposition qiymatlari bilan bir xil ataylab.

    Bu enum'ni takrorlashning sababi: PipelineConfig dlt'ni import
    qilmasligi kerak (yuqoridagi izohga qarang). Qiymatlar string
    darajasida bir xil bo'lgani uchun runner'da to'g'ridan-to'g'ri
    `.value` sifatida dlt'ga uzatiladi, hech qanday mapping jadvali
    kerak emas.
    """

    APPEND = "append"
    REPLACE = "replace"
    MERGE = "merge"


class ScheduleKind(str, Enum):
    """Foydalanuvchi UI'da tanlaydigan jadvallash turlari.

    MANUAL — hech qanday avtomatik ishga tushirish yo'q, faqat
    dashboard'dagi "Run" tugmasi orqali.
    INTERVAL — APScheduler orqali oddiy takrorlanish (masalan har soat).
    AIRFLOW — bu pipeline Airflow DAG generatoriga eksport qilinadi;
    UzPipe'ning o'z scheduler'i uni boshqarmaydi.
    """

    MANUAL = "manual"
    INTERVAL = "interval"
    AIRFLOW = "airflow"


class ScheduleConfig(BaseModel):
    kind: ScheduleKind = ScheduleKind.MANUAL
    interval_minutes: int | None = Field(
        default=None,
        description="kind=INTERVAL bo'lganda majburiy, masalan 60 = har soat",
    )

    @field_validator("interval_minutes")
    @classmethod
    def _require_interval_when_needed(cls, v: int | None, info: Any) -> int | None:
        if info.data.get("kind") == ScheduleKind.INTERVAL and not v:
            raise ValueError("kind=INTERVAL uchun interval_minutes majburiy")
        return v


class DestinationConfig(BaseModel):
    """Qayerga yuklanishi.

    `connection` maydoni ataylab Optional va `secret`likka
    e'tibor berilmagan — bu maydonning o'zi encryption qatlamidan
    o'tadimi yo'qmi, buni ConnectorManifest emas, balki
    uzpipe.store.control_store hal qiladi (destination credentials
    ham connector credentials kabi maxfiy deb qaraladi, tafsilot
    uchun control_store.py ga qarang).
    """

    connector: str = Field(..., description="'duckdb', 'postgresql', 'clickhouse', 'filesystem'")
    connection: str | None = Field(default=None, description="Connection string, DuckDB uchun shart emas")
    dataset_name: str = Field(default="raw", description="dlt dataset/schema nomi")


class QualityConfig(BaseModel):
    """4 ta SQL check — POSITIONING.md dagi 'Batteries Included' pillar'iga mos.

    Har biri Optional/None qilib qo'yilgan — foydalanuvchi UI'da
    faqat kerakli check'larni yoqadi, qolgani sukut bo'yicha
    tekshirilmaydi. Bu qat'iy majburiy qilingan bo'lsa, oddiy
    "birinchi run"da ortiqcha to'siq bo'lardi.

    NEGA `table_name` VA `freshness_column` QO'SHILDI (dastlabki
    versiyada yo'q edi)
    --------------------------------------------------------------
    Bitta pipeline bir nechta jadval yozishi mumkin (masalan
    rest_api connector bir nechta resource'dan). Check'lar QAYSI
    jadvalga tegishli ekanini bilmasa, executor buni taxmin qilishga
    majbur bo'lardi — bu noto'g'ri natija berishi mumkin. `table_name`
    None qoldirilsa, executor check'ni SHU RUN'DA YOZILGAN HAR BIR
    jadvalga qo'llaydi (qarang: quality.py); aniq bitta jadval
    ko'zda tutilsa, shu yerda ko'rsatiladi.

    `freshness_max_minutes` check'i "ma'lumot qancha eski" deb
    so'raydi, lekin buni bilish uchun QAYSI ustun sana/vaqtni
    ifodalashini bilish shart (masalan `updated_at`). Bu ustun nomi
    berilmasa, freshness check o'tkazib yuboriladi (xato emas, chunki
    ustun nomi cursor_column bilan bir xil bo'lishi ehtimoli katta,
    lekin buni avtomatik taxmin qilish xato natijaga olib kelishi
    mumkin — aniq ko'rsatilishi xavfsizroq).
    """

    row_count_min: int | None = None
    not_null_columns: list[str] = Field(default_factory=list)
    no_duplicates_key: str | None = None
    freshness_max_minutes: int | None = None
    freshness_column: str | None = Field(
        default=None,
        description="freshness_max_minutes check'i uchun sana/vaqt ustuni, masalan 'updated_at'",
    )
    table_name: str | None = Field(
        default=None,
        description=(
            "Check'lar qaysi jadvalga tegishli. None bo'lsa, run'da "
            "yozilgan har bir jadvalga qo'llaniladi."
        ),
    )


class NotifyConfig(BaseModel):
    on_failure: bool = True
    on_success: bool = False
    telegram_chat_id: str | None = None
    # telegram_bot_token BU YERDA YO'Q — bu global, foydalanuvchi darajasida
    # bitta marta sozlanadigan sozlama (bir nechta pipeline bitta botdan
    # xabar yuboradi), pipeline-darajasidagi qiymat emas. Global sozlamalar
    # uzpipe.store.control_store dagi alohida "settings" jadvalida turadi.


class PipelineConfig(BaseModel):
    """Bitta pipeline'ning to'liq, ijro etiladigan konfiguratsiyasi.

    Bu klass dashboard formasi to'ldirilgach hosil bo'ladigan YAKUNIY
    natija. Hayot sikli:

        forma qiymatlari (dict) --ConnectorManifest.validate_values()-->
        tasdiqlangan dict --PipelineConfig.model_validate()-->
        PipelineConfig --control_store.save()--> SQLite
                                |
                                v
        SQLite'dan o'qish --> PipelineConfig --pipeline_runner.run()--> dlt
    """

    name: str = Field(..., description="Foydalanuvchi bergan nom, masalan 'payme_kunlik'")
    connector_key: str = Field(..., description="ConnectorManifest.key ga mos keladi")
    source_params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Manifest fields'idan kelgan qiymatlar, key->value. "
            "Maxfiy qiymatlar bu yerda emas — ular alohida, shifrlangan "
            "holda control_store'da saqlanadi va runtime'da inject qilinadi "
            "(qarang: pipeline_runner.build_dlt_source)."
        ),
    )
    destination: DestinationConfig
    write_disposition: WriteDisposition = WriteDisposition.APPEND
    primary_key: list[str] = Field(default_factory=list)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)

    @field_validator("name")
    @classmethod
    def _name_is_filesystem_safe(cls, v: str) -> str:
        # dlt pipeline nomi sifatida ham ishlatiladi (papka nomi bo'lishi
        # mumkin) — shuning uchun xavfsiz belgilar bilan cheklanadi.
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Pipeline nomi bo'sh bo'lishi mumkin emas")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not set(cleaned) <= allowed:
            raise ValueError(
                "Pipeline nomida faqat harf, raqam, '_' va '-' bo'lishi mumkin"
            )
        return cleaned

    def to_storable_dict(self) -> dict[str, Any]:
        """SQLite'ga yozish uchun — maxfiy bo'lmagan qiymatlarning to'liq ko'rinishi.

        Chaqiruvchi (control_store) bu dict'ni to'g'ridan-to'g'ri JSON
        ustuniga yozadi. Maxfiy qiymatlar chaqiruvchi tomonidan OLDINDAN
        source_params'dan olib tashlangan bo'lishi kutiladi — bu funksiya
        buni o'zi TEKShIRMAYDI, chunki "qaysi kalit maxfiy" bilimi
        manifestda, bu klassda emas (qarang: ConnectorManifest.secret_keys).
        """
        return self.model_dump(mode="json")
