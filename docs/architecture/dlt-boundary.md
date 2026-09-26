# dlt chegarasi: nima bepul, nima tijorat

**Bu eng muhim hujjat loyihada.** Bitta marta bu chegara noto'g'ri
chizilgani uchun (`dlt dashboard` = tijorat paket ekanligi kech
aniqlangan, qarang [`dashboard.md`](dashboard.md)) — endi har bir
yangi dlt imkoniyati ISHLATISHDAN OLDIN shu jadvalga qarab tekshiriladi,
va jadvalning o'zi ham **amalda ishga tushirib** (`pip install`,
qidiruv natijasiga ishonmasdan) tasdiqlangan.

## Qoida (har safar yangi dlt funksiyasi ko'rilganda qo'llaniladi)

1. Paket nomini toping (`pip show <paket>`)
2. `Requires-Dist` yoki PyPI tavsifida "license", "EULA", "waiting list", "commercial" so'zlarini qidiring
3. Agar shubha bo'lsa — **o'rnatib ko'ring**. Litsenziya so'ralsa yoki xato chiqsa, bu tijorat.
4. Natijani shu faylga qo'shing (yangi qator, tegishli bo'limga)

## Tasdiqlangan: dlt (Apache 2.0, `pip install dlt`) — TO'LIQ BEPUL

| Imkoniyat | Nima beradi | Qayerda ishlatiladi (Chumoli'da) |
|---|---|---|
| `rest_api_source`, `sql_database`, `filesystem` | Universal source'lar | `src/chumoli/connectors/rest_api/`, `sql_database/` |
| Schema inference, incremental state, load packages | Pipeline engine o'zagi | `pipeline_runner.py` orqali |
| `schema_contract` (`{"tables": "evolve/freeze", "columns": ..., "data_type": ...}`) | Strukturaviy sifat nazorati: yangi jadval/ustun/tur kelganda nima qilish | Hali ulanmagan — [`quality-and-reliability.md`](quality-and-reliability.md)da rejalashtirilgan |
| CLI: `dlt pipeline <name> trace` | Oxirgi run'ning to'liq izi | Mavjud, lekin UI'da hali ko'rsatilmagan |
| CLI: `dlt pipeline <name> failed-jobs` | Muvaffaqiyatsiz job'lar va xato matni | xuddi shu |
| CLI: `dlt pipeline <name> sync` | Mahalliy holatni destination'dan tiklaydi | xuddi shu |
| CLI: `dlt pipeline <name> drop <resource>` | Bitta resource holatini tiklaydi | xuddi shu |
| CLI: `dlt pipeline <name> drop-pending-packages` | Yarim yuklangan package'larni tozalaydi | xuddi shu |
| Avtomatik retry (transient xatolar) + terminal xato aniqlash | O'zi qayta uradi yoki to'xtaydi | Hech narsa qilinmaydi — dlt o'zi boshqaradi |
| `dlt.helpers.airflow_helper.PipelineTasksGroup` | Pipeline'ni Airflow task group sifatida o'raydi, retry policy, log routing | Ishlatilmaydi — Chumoli'da Airflow integratsiyasi yo'q |
| `dlt deploy <pipeline> airflow-composer` | Tayyor Airflow DAG generatsiya qiladi | Ishlatilmaydi — dlt'ning o'zida bor, Chumoli qayta yozmaydi va UI'ga chiqarmaydi |

**Muhim eslatma `dlthub.com/products/orchestration` haqida:** bu sahifa
domen nomi bo'yicha tijorat ko'rinadi, lekin tavsiflagan narsasi
(`PipelineTasksGroup`, `dlt deploy`) — dlt'ning ochiq GitHub repo'sida
(`dlt-hub/dlt/blob/devel/dlt/helpers/airflow_helper.py`), hech qanday
litsenziya talab qilmaydi. **Domen nomiga qarab xulosa chiqarmang —
paketning o'ziga qarang.**

## Tasdiqlangan: dltHub (`pip install dlt[hub]` → `dlthub`, `dlthub-client`) — TIJORAT

| Imkoniyat | Holat | Nega ishlatilmaydi |
|---|---|---|
| `dlt dashboard` buyrug'i | Tijorat, EULA, "Free tier" ham litsenziya fayli talab qiladi | [`dashboard.md`](dashboard.md) — batafsil tarix |
| `is_in()`, `is_unique()`, `is_primary_key()` (content-darajasidagi quality) | dltHub'ning rasmiy hujjatida ochiq: *"dltHub provides... Built-in data quality checks"* | O'zimiz yozamiz — [`quality-and-reliability.md`](quality-and-reliability.md) |
| dltHub AI Workbench (schema-aware avto-check generatsiya) | *"under development... Join dltHub early access"* — hali chiqmagan, kelajakda ham tijorat bo'lishi ehtimoli baland | Ishlatilmaydi |
| dltHub "Advanced" metrics/checks (`DltSource` sifatida) | Rasmiy hujjatda: *"🚧 This feature is under development"* | Ishlatilmaydi |

**Tekshirish dalili (2026-09-17, amalda bajarilgan):**
```
$ pip install "dlt[hub]"
# -> dlthub-0.30.0, dlthub-client-0.28.4 o'rnatiladi (ochiq dashboard EMAS)

$ pip show dlthub
# Requires: dlthub-client>=0.28.1
# (PyPI tavsifida: "commercial extension to dlt... requires a license")

$ dlt dashboard --edit
# (dlt[hub] o'rnatilmasdan) -> "WARNING: Install dlt[hub] for workspace dashboard"
```

## Xulosa: qaror qoidasi

- **dlt (asosiy paket, `pip install dlt`) ichida bo'lgan HAR NARSA** — ishlatiladi, qayta yozilmaydi.
- **`dlt[hub]` yoki `dlthub` talab qiladigan HAR NARSA** — ishlatilmaydi. Dashboard uchun `src/chumoli/static/index.html` (o'zimizniki); boshqa imkoniyatlar uchun ochiq kodli muqobil yoki o'zimiznikini yozamiz.
- Yangi dlt versiyasi chiqqanda (yoki yangi imkoniyat haqida eshitilganda), **bu jadval yangilanadi, taxmin qilinmaydi.**
