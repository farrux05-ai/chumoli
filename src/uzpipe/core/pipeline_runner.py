"""
uzpipe.core.pipeline_runner
==============================

Butun fundamentning "so'nggi qadami": ControlStore'dan o'qilgan
PipelineConfig + secrets'ni olib, HAQIQIY dlt.pipeline().run() ni
chaqiradi.

NEGA BU FAYL ALOHIDA, ConnectorRegistry YOKI PipelineConfig ICHIGA
YOZILMAGAN
--------------------------------------------------------------------
Bu qatlamlar orasidagi "orkestratsiya" kodi — u boshqa hech bir
qatlamga tegishli emas:
  - ConnectorRegistry connectorlarni BILADI, lekin ularni QANDAY
    ISHGA TUSHIRISHNI bilmasligi kerak.
  - PipelineConfig ma'lumotni SAQLAYDI, lekin dlt haqida hech narsa
    bilmasligi kerak (config.py dagi izohga qarang).
  - ControlStore credentials'ni SAQLAYDI/O'QIYDI, lekin ularni
    ishlatishni bilmasligi kerak.

Agar orkestratsiya shulardan biriga yozilsa, o'sha modul boshqa
barcha modullarga bog'liq bo'lib qoladi (masalan PipelineConfig dlt'ni
import qiladi) — bu "har bir qatlam faqat pastki qatlamni biladi"
degan toza arxitekturani buzadi. `pipeline_runner` ATAYLAB eng
YUQORIDA turadi: u hammasini biladi, lekin hech kim uni bilishi
shart emas.

QUALITY CHECKS ARE CALLED HERE, AFTER run() SUCCEEDS
-------------------------------------------------------------
`run_pipeline_by_name` calls `uzpipe.core.quality.run_quality_checks`
after a successful `pipeline.run()`, using the same `dlt.Pipeline`
object (no reconnect) and `PipelineConfig.quality`. This was
originally deferred ("not called here") until the quality executor
itself existed — see docs/architecture/quality-and-reliability.md for
why quality checks are content-level (row count, nulls, duplicates,
freshness) and deliberately separate from dlt's own structural
guarantees (schema_contract), which this runner does not touch at
all — schema_contract is set at the connector/resource level, not
here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import dlt

from uzpipe.connectors.base import BaseUZConnector, registry
from uzpipe.core.config import PipelineConfig
from uzpipe.core.quality import QualityReport, run_quality_checks
from uzpipe.store.control_store import ControlStore, StoredPipeline


@dataclass
class RunResult:
    """dlt'ning `LoadInfo` obyektini o'raydi, UzPipe-friendly shaklda.

    dlt.pipeline().run() ning o'z natijasi (`LoadInfo`) juda ko'p
    ichki tafsilotni o'z ichiga oladi. Bu wrapper dashboard/CLI uchun
    kerak bo'ladigan minimal, barqaror kontraktni beradi — agar dlt
    LoadInfo strukturasini o'zgartirsa, faqat shu klassni yaratuvchi
    kod (pastda) moslashadi, dashboard kodi tegilmaydi.

    NEGA `success` FAQAT LOAD MUVAFFAQIYATINI BILDIRADI, QUALITY
    NATIJASINI EMAS
    --------------------------------------------------------------
    Load muvaffaqiyatli bo'lib, lekin quality check muvaffaqiyatsiz
    bo'lishi mumkin (masalan ma'lumot yuklandi, lekin kutilganidan
    kamroq qator keldi). Bularni bitta boolean'ga birlashtirish bu
    ikki xil signalni yashiradi — dashboard ikkalasini ALOHIDA
    ko'rsatishi kerak ("yuklandi, lekin sifat tekshiruvi
    muvaffaqiyatsiz" — bu "umuman yuklanmadi"dan farqli holat va
    foydalanuvchiga boshqacha ta'sir qiladi). `quality_report` shu
    uchun alohida maydon: `success and quality_report.all_passed`
    chaqiruvchi tomonda (dashboard/CLI) hisoblanadi, bu yerda emas.
    """

    pipeline_name: str
    load_info: Any  # dlt.pipeline.LoadInfo — ataylab Any, dlt ichki turi
    row_counts: dict[str, int]
    quality_report: QualityReport

    @property
    def success(self) -> bool:
        return not self.load_info.has_failed_jobs


def build_dlt_pipeline(config: PipelineConfig) -> dlt.Pipeline:
    """PipelineConfig.destination'dan dlt.Pipeline obyektini yasaydi.

    Bu funksiya destination-mapping mantig'ini bitta joyda ushlab
    turadi. `connector` maydoni ("duckdb", "postgresql", "clickhouse",
    "filesystem") to'g'ridan-to'g'ri dlt'ning `destination=` argumentiga
    mos keladi — dlt buni o'zi tanib oladi, qo'shimcha mapping jadvali
    kerak emas (bu ataylab shunday tanlangan: DestinationConfig.connector
    qiymatlari dlt'ning nomlash konventsiyasidan ataylab chetga
    chiqmaydi).
    """
    destination_kwargs: dict[str, Any] = {}
    if config.destination.connection:
        destination_kwargs["credentials"] = config.destination.connection

    if destination_kwargs:
        # Modulning atributiga oddiy getattr() orqali murojaat qilamiz —
        # `dlt.destinations` bu holatda "har qanday nomdagi destination
        # factory'ni ber" degan lazy-module bo'lib ishlaydi (dlt buni shu
        # tarzda loyihalagan). `module.__getattr__(name)` ni to'g'ridan-
        # to'g'ri chaqirish Python'da NOTO'G'RI shakl — bu maxsus metod
        # faqat `getattr(module, name)` orqali chaqirilganda ishlaydi.
        destination_factory = getattr(dlt.destinations, config.destination.connector)
        destination: Any = destination_factory(**destination_kwargs)
    else:
        destination = config.destination.connector

    return dlt.pipeline(
        pipeline_name=config.name,
        destination=destination,
        dataset_name=config.destination.dataset_name,
    )


def run_pipeline_by_name(name: str, store: ControlStore | None = None) -> RunResult:
    """Eng yuqori darajadagi kirish nuqtasi — CLI va dashboard shu funksiyani chaqiradi.

    Bu funksiya ATAYLAB "nom" bilan ishlaydi (PipelineConfig obyekti
    bilan emas) — chunki chaqiruvchi tomon (CLI: `uzpipe run
    payme_kunlik`, dashboard: "Run" tugmasi) doim faqat nomni biladi,
    to'liq config'ni emas. Config va secrets'ni yuklash bu funksiyaning
    o'zining ishi, chaqiruvchidan yashirilgan.
    """
    store = store or ControlStore()
    stored = store.load(name)
    if stored is None:
        raise KeyError(f"Pipeline '{name}' topilmadi")

    connector = registry.get(stored.config.connector_key)
    return _execute(stored, connector)


def _execute(stored: StoredPipeline, connector: BaseUZConnector) -> RunResult:
    """Haqiqiy dlt chaqiruvi — connector'dan source, config'dan pipeline yasab, run() qiladi.

    Bu funksiya alohida ajratilgan (public run_pipeline_by_name'dan)
    chunki test yozishda ControlStore/registry'ni chetlab o'tib,
    to'g'ridan-to'g'ri StoredPipeline + connector bilan sinash kerak
    bo'ladi — bu SQLite fayl yaratishga hojat qoldirmaydi.

    NEGA QUALITY CHECK LOAD MUVAFFAQIYATSIZ BO'LSA O'TKAZIB YUBORILADI
    --------------------------------------------------------------
    Agar load o'zi muvaffaqiyatsiz bo'lsa (masalan tarmoq xatosi),
    jadval umuman yozilmagan yoki yarim yozilgan bo'lishi mumkin.
    Bunday holatda "row_count_min" yoki "not_null" kabi check'larni
    ishga tushirish yo'q jadvalga SQL so'rov yuborishga yoki
    chalkash natijaga olib keladi. Load statusi allaqachon
    muvaffaqiyatsizlikni bildiradi — quality check bu signalni
    takrorlashi shart emas.
    """
    source = connector.build_dlt_source(stored.config.source_params, stored.secrets)
    pipeline = build_dlt_pipeline(stored.config)

    load_info = pipeline.run(
        source,
        write_disposition=stored.config.write_disposition.value,
        primary_key=stored.config.primary_key or None,
    )

    load_succeeded = not load_info.has_failed_jobs
    row_counts = _get_row_counts(pipeline) if load_succeeded else {}

    if load_succeeded:
        quality_report = run_quality_checks(
            pipeline, stored.config.quality, tables_written=list(row_counts.keys())
        )
    else:
        quality_report = QualityReport()

    return RunResult(
        pipeline_name=stored.config.name,
        load_info=load_info,
        row_counts=row_counts,
        quality_report=quality_report,
    )


def _get_row_counts(pipeline: dlt.Pipeline) -> dict[str, int]:
    """Har bir foydalanuvchi jadvali uchun qator sonini destination'dan to'g'ridan-to'g'ri o'qiydi.

    NEGA BU FUNKSIYA `load_info.metrics` NI EMAS, `pipeline.sql_client()`
    NI ISHLATADI (bu funksiyaning dastlabki versiyasi `LoadInfo.metrics`
    ni parse qilishga harakat qilgan edi — HAQIQATDA SINAB KO'RILGANDA
    aniqlandiki: `LoadInfo.metrics` HAM, `LoadInfo.load_packages` HAM
    qator sonini umuman saqlamaydi (dlt 1.30) — ular faqat fayl/job
    metadata'sini (table_name, file_path, holat) saqlaydi, qator soni
    emas. Bu ikki marta amalda tekshirilgan (`LoadJobMetrics` va
    `LoadJobInfo` NamedTuple'larining `_fields`'i to'g'ridan-to'g'ri
    chop etilib) — taxmin emas.

    To'g'ri yechim: `pipeline.default_schema.tables` orqali qaysi
    jadvallar HAQIQATDA yaratilganini bilib (ichki `_dlt_*` jadvallarni
    filtrlab), keyin `pipeline.sql_client()` orqali (xuddi
    quality.py dagi check'lar kabi, bir xil, allaqachon sinalgan
    mexanizm) har biriga `SELECT COUNT(*)` yuboradi. Bu destination-
    agnostik (DuckDB, Postgres — bir xil kod ishlaydi) va haqiqiy
    qator sonini beradi, chunki manba — destination'ning o'zi, dlt'ning
    ichki metadata formati emas.

    Bu funksiya `load_succeeded=True` bo'lgandagina chaqiriladi
    (_execute'da) — muvaffaqiyatsiz load'da jadvallar yo'q yoki
    yarim bo'lishi mumkin, bu holatda SQL so'rov ma'nosiz.
    """
    user_tables = [
        table_name
        for table_name in pipeline.default_schema.tables.keys()
        if not table_name.startswith("_dlt")
    ]

    counts: dict[str, int] = {}
    with pipeline.sql_client() as client:
        for table_name in user_tables:
            result = client.execute_sql(f'SELECT COUNT(*) FROM "{table_name}"')
            counts[table_name] = result[0][0]
    return counts
