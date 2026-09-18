"""
uzpipe.connectors.base
=========================

BaseUZConnector protocol va ConnectorRegistry.

NEGA PROTOCOL, ABSTRACT BASE CLASS EMAS
--------------------------------------------
POSITIONING.md da aytilganidek, mavjud tizim "Protocol-based framework"
ishlatadi (`authenticate`, `paginate`, `rate_limit`, `validate`). Bu
yerda o'sha tamoyil davom ettirildi va kengaytirildi: `typing.Protocol`
duck-typing imkonini beradi — connector muallifi hech qanday
inheritance zanjiriga majbur bo'lmaydi, faqat kerakli metodlarni
implement qilsa bo'ldi. Bu ayniqsa dlt bilan integratsiyada muhim:
`rest_api` yoki `sql_database` kabi dlt'ning TAYYOR source'lari uchun
UzPipe connector'i faqat "yupqa moslashtiruvchi" (thin adapter) bo'lishi
kerak, ular dlt'ning ichki class hierarchiyasidan meros olmaydi.

NEGA `build_dlt_source` — YAGONA MAJBURIY METOD
----------------------------------------------------
Dastlab to'rtta metod (`authenticate`, `paginate`, `rate_limit`,
`validate`) alohida-alohida talab qilinishi mumkin edi. Lekin amalda
bularning barchasi FAQAT bitta maqsad uchun kerak: oxir-oqibat ishlaydigan
`dlt.sources.DltSource` obyekti hosil qilish. Agar connector bu to'rtta
tashvishni o'zi qanday hal qilishni tanlasa (masalan `rest_api_source()`
chaqirib, pagination'ni dlt'ning o'ziga topshirsa), bu uning ichki
ishi — protocol bunga aralashmasligi kerak. Shuning uchun protocol
minimal: bitta metod, `build_dlt_source(secrets) -> DltSource`.
Bu connector muallifiga MAKSIMAL erkinlik beradi, lekin UzPipe'ning
qolgan qismiga (runner, dashboard) FAQAT bitta kontraktni bilish kifoya.

NEGA REGISTRY ALOHIDA KLASS, ODDIY DICT EMAS
--------------------------------------------------
Oddiy global dict (`CONNECTORS = {}`) ham ishlagan bo'lardi, lekin
ConnectorRegistry ikkita qo'shimcha narsa beradi:
  1. Ro'yxatga olishda manifest.key bilan class mosligini tekshiradi
     (typo'lar ishga tushish vaqtida aniqlanadi, run vaqtida emas).
  2. `dlt_source_factory` string (manifest.py dagi izohga qarang)
     bilan haqiqiy klass orasidagi bog'lanishni bitta joyda ushlab
     turadi — bu import qilingan modullarni kuzatib borish uchun
     yagona manzil.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from uzpipe.core.manifest import ConnectorManifest


@runtime_checkable
class BaseUZConnector(Protocol):
    """Har bir connector shu protocol'ga mos kelishi kerak.

    `manifest` — class atributi (instance emas), chunki manifestga
    ulanish uchun connector'ni instantiate qilish shart bo'lmasligi
    kerak (masalan dashboard faqat forma chizish uchun manifestni
    o'qiydi, hech qanday connector obyektini yaratmasdan).
    """

    manifest: ConnectorManifest

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        """dlt.sources.DltSource (yoki unga mos ro'yxatdan o'tgan resource) qaytaradi.

        `params` — ConnectorManifest.fields dagi maxfiy BO'LMAGAN
        qiymatlar (PipelineConfig.source_params).
        `secrets` — ConnectorManifest.secret_keys() ro'yxatiga mos,
        deshifrlangan qiymatlar (ControlStore.load() dan keladi).

        Bu ikkisini ATAYLAB ajratib yuborish — connector kodi ichida
        ham "bu qiymat qayerdan kelgani" (config'danmi, maxfiy
        do'kondanmi) doim aniq bo'lishi uchun. Connector muallifi
        tasodifan maxfiy qiymatni oddiy params sifatida yozib qo'yishi
        mumkin emas, chunki ular funksiya imzosida jismonan boshqa
        argument.
        """
        ...


class ConnectorRegistry:
    """Barcha ro'yxatdan o'tgan connectorlarni ushlab turadigan markaz.

    Dashboard, CLI va pipeline_runner — barchasi FAQAT shu klass orqali
    connectorlarni topadi. Hech kim `uzpipe.connectors.payme_uz.connector`
    dan to'g'ridan-to'g'ri import qilmaydi (bitta joydan tashqari — bu
    faylning pastidagi `register_builtin_connectors()`), chunki bu
    "qaysi connectorlar mavjud" degan bilimni bitta manzilda ushlab
    turadi.
    """

    def __init__(self) -> None:
        self._connectors: dict[str, BaseUZConnector] = {}

    def register(self, connector: BaseUZConnector) -> None:
        manifest = connector.manifest
        if manifest.key in self._connectors:
            raise ValueError(f"Connector '{manifest.key}' allaqachon ro'yxatdan o'tgan")
        if not isinstance(connector, BaseUZConnector):
            # runtime_checkable Protocol — bu metod mavjudligini
            # tekshiradi, imzoni emas. Shunga qaramay, bu erta signalni
            # beradi: agar kimdir `build_dlt_source` metodini butunlay
            # unutib qo'ysa, xato ro'yxatga olish vaqtida chiqadi.
            raise TypeError(
                f"'{manifest.key}' BaseUZConnector protocol'iga mos kelmaydi "
                "(build_dlt_source metodi topilmadi)"
            )
        self._connectors[manifest.key] = connector

    def get(self, key: str) -> BaseUZConnector:
        if key not in self._connectors:
            raise KeyError(
                f"Connector '{key}' topilmadi. Ro'yxatdagilar: {list(self._connectors)}"
            )
        return self._connectors[key]

    def get_manifest(self, key: str) -> ConnectorManifest:
        return self.get(key).manifest

    def all_manifests(self) -> list[ConnectorManifest]:
        """Dashboard'ning connector tanlash ekrani uchun — barcha manifestlar.

        Bu metod nomi ataylab `all_manifests`, `all_connectors` emas —
        chunki forma chizish uchun connector OBYEKTI emas, faqat uning
        manifesti kerak. Bu farq kichik ko'rinsa-da, "dashboard faqat
        manifestga tegishi kerak, connector implementatsiyasiga emas"
        degan qatlamlar ajratmasini kod darajasida mustahkamlaydi.
        """
        return [c.manifest for c in self._connectors.values()]


# Bitta, jarayon-darajasidagi global registry. Kelajakda test'lar
# uchun alohida ConnectorRegistry() instance yaratish kerak bo'lsa,
# bu ataylab oson — konstruktor argumentsiz chaqiriladi.
registry = ConnectorRegistry()
