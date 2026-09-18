"""
uzpipe.store.control_store
=============================

Pipeline konfiguratsiyalarini va ularning maxfiy credentials'ini
saqlovchi qatlam.

NEGA SQLITE, DUCKDB EMAS (ARCHITECTURE_DECISION.md 3.4 bandiga qarang)
--------------------------------------------------------------------------
Qisqacha takror: bu fayl TEZ-TEZ YOZILADI (dashboard'dan pipeline
qo'shish/o'zgartirish har safar bu yerga yozadi). DuckDB analitik
so'rovlar (ko'p o'qish, kam yozish) uchun optimallashtirilgan va
concurrent write'larda SQLite kabi ishonchli emas. `uzpipe_runs.duckdb`
(mavjud kod, bu faylda tegilmaydi) — run TARIXI uchun, bu FAYL esa
pipeline KONFIGURATSIYASI uchun. Ikkalasi butunlay boshqa yozish
naqshiga ega, shuning uchun boshqa DB.

NEGA CREDENTIALS VA CONFIG BIR JADVALDA (ajratilgan USTUNLARDA)
--------------------------------------------------------------------
Muqobil dizayn: alohida "credentials" jadvali, pipeline_id orqali
bog'langan. Bu yerda ataylab RAD ETILDI, chunki:
  1. Bitta pipeline = bitta credential to'plami (1:1 munosabat, hech
     qachon 1:many emas) — alohida jadval faqat JOIN qo'shadi, foyda
     bermaydi.
  2. Ikki jadval degani ikki joyda "transaction consistency" masalasi
     (pipeline yaratildi, lekin credentials yozilmadi — degan holatlar).
     Bitta qatorga yozish bu muammoni butunlay yo'qotadi.

NEGA `secrets_json` BITTA USTUN, HAR BIR SECRET UCHUN ALOHIDA USTUN EMAS
------------------------------------------------------------------------------
Har bir connector turli sonli va turli nomli maxfiy maydonga ega
(Payme'da 2 ta, Didox'da 1 ta). Agar har biri uchun alohida ustun
ochilsa, schema har yangi connector uchun ALTER TABLE talab qiladi —
bu aynan manifest-driven arxitekturaning oldini olishga harakat
qilayotgan narsasi. Shifrlangan qiymatlar bitta JSON blob sifatida
saqlanadi; qaysi kalitlar ichida borligi ConnectorManifest orqali
ma'lum, DB schema orqali emas.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from uzpipe.core.config import PipelineConfig
from uzpipe.core.manifest import ConnectorManifest
from uzpipe.security.crypto import CredentialCipher

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipelines (
    name TEXT PRIMARY KEY,
    connector_key TEXT NOT NULL,
    config_json TEXT NOT NULL,      -- PipelineConfig, maxfiy bo'lmagan qiymatlar
    secrets_json TEXT NOT NULL,     -- {key: shifrlangan_qiymat}, faqat manifest.secret_keys()
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class StoredPipeline:
    """`load()` natijasi: config + hali shifrlanmagan (deshifrlangan) secrets.

    Bu ataylab PipelineConfig'ning o'zi EMAS — chunki PipelineConfig.
    source_params ichida secret qiymatlar YO'Q (config.py dagi izohga
    qarang). StoredPipeline ikkalasini birlashtirib, runner'ga
    "to'liq, ishga tayyor" ma'lumot beradi.
    """

    config: PipelineConfig
    secrets: dict[str, str]


class ControlStore:
    """Pipeline configlar uchun SQLite ustidagi yupqa qatlam.

    Bu klass ataylab dlt haqida hech narsa bilmaydi — u faqat
    PipelineConfig'larni saqlaydi/o'qiydi. dlt'ga ulanish
    `uzpipe.core.pipeline_runner` da sodir bo'ladi.
    """

    def __init__(self, db_path: Path | None = None, cipher: CredentialCipher | None = None) -> None:
        self._db_path = db_path or self._default_db_path()
        self._cipher = cipher or CredentialCipher()
        self._init_schema()

    @staticmethod
    def _default_db_path() -> Path:
        home = Path.home() / ".uzpipe"
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        return home / "uzpipe_control.db"

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False: dashboard (Marimo) va CLI turli
        # thread/process'lardan kirishi mumkin. SQLite'ning o'z fayl
        # darajasidagi locking mexanizmi (WAL mode) bunga yetadi —
        # qo'shimcha connection pool kerak emas, chunki yozish
        # chastotasi past (foydalanuvchi harakati bilan cheklangan).
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def save(
        self,
        config: PipelineConfig,
        raw_secrets: dict[str, str],
        manifest: ConnectorManifest,
    ) -> None:
        """Pipeline'ni yaratadi yoki (nom mos kelsa) yangilaydi.

        `raw_secrets` — foydalanuvchi formada kiritgan, HALI SHIFRLANMAGAN
        qiymatlar (masalan {"api_key": "sk_live_abc123"}). Bu funksiya
        ularni manifest.secret_keys() bo'yicha filtrlaydi va faqat
        shu kalitlarni shifrlaydi — manifestda "secret" deb
        belgilanmagan hech narsa shifrlanmaydi (chunki shifrlash
        qaytarib bo'lmaydigan performance/murakkablik narxi, kerak
        joyda ishlatiladi).

        Diqqat: `config.source_params` bu yerga kelganda MAXFIY
        QIYMATLARSIZ bo'lishi kutiladi (chaqiruvchi ularni oldindan
        ajratgan). Bu funksiya buni tekshiradi va agar manifest
        bo'yicha maxfiy bo'lishi kerak bo'lgan kalit source_params
        ichida ham topilsa — xato ko'taradi. Bu himoya qatlami:
        agar kimdir chaqiruv tartibini buzsa (masalan to'g'ridan-to'g'ri
        forma dict'ini config.source_params'ga qo'ysa), parol
        tasodifan plain-text saqlanib qolishining oldini oladi.
        """
        secret_keys = set(manifest.secret_keys())
        leaked = secret_keys & set(config.source_params.keys())
        if leaked:
            raise ValueError(
                f"Maxfiy maydonlar source_params ichida topildi: {leaked}. "
                "Bu maydonlar faqat raw_secrets orqali uzatilishi kerak."
            )

        missing = secret_keys - set(raw_secrets.keys())
        if missing:
            raise ValueError(f"Quyidagi maxfiy maydonlar yetishmayapti: {missing}")

        encrypted_secrets = self._cipher.encrypt_dict(
            {k: v for k, v in raw_secrets.items() if k in secret_keys}
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipelines (name, connector_key, config_json, secrets_json)
                VALUES (:name, :connector_key, :config_json, :secrets_json)
                ON CONFLICT(name) DO UPDATE SET
                    connector_key = excluded.connector_key,
                    config_json = excluded.config_json,
                    secrets_json = excluded.secrets_json,
                    updated_at = datetime('now')
                """,
                {
                    "name": config.name,
                    "connector_key": config.connector_key,
                    "config_json": json.dumps(config.to_storable_dict()),
                    "secrets_json": json.dumps(encrypted_secrets),
                },
            )

    def load(self, name: str) -> StoredPipeline | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT config_json, secrets_json FROM pipelines WHERE name = ?",
                (name,),
            ).fetchone()

        if row is None:
            return None

        config = PipelineConfig.model_validate(json.loads(row["config_json"]))
        encrypted_secrets: dict[str, str] = json.loads(row["secrets_json"])
        secrets = self._cipher.decrypt_dict(encrypted_secrets)
        return StoredPipeline(config=config, secrets=secrets)

    def list_all(self) -> list[dict[str, Any]]:
        """Dashboard'ning pipeline ro'yxati uchun — secrets QAYTARILMAYDI.

        Ataylab shifrlangan holatida ham qaytarilmaydi: ro'yxat
        ko'rinishida credentials umuman kerak emas, shuning uchun
        eng xavfsiz yo'l — ularni bu metodning natijasidan butunlay
        chiqarib tashlash. Kimdir credentials kerak bo'lsa, aniq
        `load(name)` chaqirishi kerak — bu "nima uchun kerakligini
        bilib turib so'rash" degan niyatni ko'rsatadi.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, connector_key, config_json, created_at, updated_at "
                "FROM pipelines ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {
                "name": r["name"],
                "connector_key": r["connector_key"],
                "config": json.loads(r["config_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def delete(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pipelines WHERE name = ?", (name,))
