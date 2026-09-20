# Chumoli — Connector Strategy

**Maqsad:** ko‘p connector emas — barqaror, ishlatiladigan, mijoz chaqiradigan connectorlar.  
**Model:** open core. Hammasi ochiq emas; asos bepul, UZ moat va SLA — tijorat.  
**Sana:** 2026-09-18  
**Bog‘liqlik:** Claude/dashboard migratsiyasidan mustaqil; fundament + bozor + dlt faktlariga asoslangan.

---

## 1. Asosiy printsiplar

| # | Qoida | Nima uchun |
|---|--------|------------|
| 1 | **Sifat > son** | Airbyte 600+ connector, lekin long-tail sifati past; Fivetran 500+, lekin qimmat va regional yo‘q. Biz 8–15 ta **ishlaydigan** connector bilan yutamiz. |
| 2 | **Mijoz chaqirganini yozamiz** | Katalog uchun yozilmaydi. Birinchi haqiqiy mijoz / pilot so‘ragan source birinchi navbatda. |
| 3 | **dlt allaqachon bajaradiganini qayta yozmaymiz** | Core source’lar thin wrapper. Nom foydalanuvchi tilida: `PostgreSQL`, `MySQL`, `REST API`, `Filesystem` — ichki `sql_database` emas. |
| 4 | **UZ = moat** | Payme, Click, 1C, Didox, Soliq — Fivetran/Airbyte hech qachon to‘liq qilmaydi. Bu tijorat qiymati. |
| 5 | **AI zamonida generic REST arzonlashdi** | Oddiy Bearer/API-key REST — foydalanuvchi o‘zi yoki AI yozishi mumkin. Bizning qiymat: maxsus auth (JSON-RPC, HMAC), lokal hujjatlar, barqarorlik, support. |

---

## 2. dlt’da nima bor (birinchi chiqariladi)

### Core sources (dlt ichida, bepul, eng ko‘p ishlatiladi)

| dlt ichki nom | **Chumoli UI nomi** | Nima beradi | Holat |
|---------------|-------------------|--------------|--------|
| `sql_database` | **PostgreSQL** | SQLAlchemy orqali Postgres | Wrap qilinadi (mavjud) |
| `sql_database` | **MySQL** | MySQL / MariaDB | Wrap qilinadi (mavjud) |
| `sql_database` | **SQL Server** (ixtiyoriy) | MSSQL | Keyinroq, talab bo‘lsa |
| `rest_api` | **REST API** | Har qanday REST (auth, pagination, incremental) | Wrap qilinadi (mavjud) |
| `filesystem` | **Filesystem / S3** | Local, S3, GCS, Azure, SFTP; CSV/JSONL/Parquet | Hali yo‘q — Phase 0 |

**Muhim:** foydalanuvchi “sql_database” deb ko‘rmaydi. Kartochkada **PostgreSQL**, **MySQL**, **REST API**, **S3 / Files** ko‘rinadi. Ichida bitta `sql_database` adapter, lekin manifest alohida (turli default credential field’lar).

### Verified sources (dlt-hub/verified-sources, `dlt init`)

Telemetriyaga ko‘ra core eng ko‘p ishlatiladi; verified — mashhur SaaS uchun.

**UZ bozorida ham uchraydiganlar (prioritet tartibida):**

| Source | Nega UZ uchun | Tavsiya |
|--------|----------------|---------|
| **Google Analytics** | Marketing / e-com | Phase 2 — wrap yoki thin adapter |
| **Google Sheets** | Operatsion jadvallar | Phase 2 |
| **Facebook Ads / Google Ads** | Reklama xarajati | Phase 2 (talab bo‘lsa) |
| **Stripe** | Xalqaro to‘lov (cheklangan UZ) | Past prioritet |
| **Shopify** | E-com (Uzum/mahalliy emas) | Past |
| **HubSpot / Salesforce** | CRM (katta kompaniyalar) | Phase 3 / enterprise |
| **MongoDB** | NoSQL app DB | Phase 2 agar mijoz so‘rasa |
| **Postgres Replication** | CDC | Keyinroq (murakkab) |

**Yozilmaydi (hozir):** Chess, Mux, Workable, Scrapy demo’lari — katalog to‘ldirish uchun emas.

---

## 3. Oʻzbekiston bozori — nima chaqiriladi

Integratsiya agentliklari, e-com, fintech, 1C/Didox hujjatlariga asosan:

### A. To‘lovlar (eng yuqori talab)

| Source | Qamrov | Integratsiya qiyinligi | Izoh |
|--------|--------|------------------------|------|
| **Click** | ~95% smartfon | O‘rtacha | Merchant API |
| **Payme** | ~85% | Qiyinroq (JSON-RPC 2.0) | TBC/Payme stack |
| **Uzum** (to‘lov) | O‘sib borayotgan | O‘rtacha | Marketplace + to‘lov |
| Uzcard / Humo | Karta | Bank orqali qiyin | Hozir past prioritet |

E-com minimal to‘plam: **Click + Payme**. Bularsiz UZ merchant deyarli ishlamaydi.

### B. Hisob / ERP / hujjat

| Source | Nega muhim |
|--------|------------|
| **1C** | Dehqonchilikdan bankgacha — deyarli universal buxgalteriya |
| **Didox** | E-invoicing / ЭДО; Soliq bilan bog‘liq |
| **MoySklad** | Ombor + savdo (o‘sib borayotgan) |
| **Soliq / my.soliq** | Hisobot, STIR, QQS — API murakkab, ERI/E-IMZO |

### C. Universal (har qanday kompaniya)

| Source | Nega |
|--------|------|
| **PostgreSQL / MySQL** | App DB → warehouse |
| **REST API** | Ichki API, custom SaaS |
| **Filesystem / S3** | CSV dump, data lake |

### D. Ish e’lonlari / stack signallari (Toshkent)

Data Engineer vakansiyalarida tez-tez: **PostgreSQL, ClickHouse, Python, Airflow, Airbyte, Oracle, Greenplum**.  
Mahalliy “Payme connector” degan ochiq lavozim kam — lekin integratsiya agentliklari va fintech ichida **Payme/Click/1C** doimiy talab.  
Xulosa: global tool’lar Postgres/ClickHouse’ni qamrab oladi; **UZ to‘lov + 1C + Didox** bo‘shliq — shu yerda moat.

---

## 4. Open core: nima bepul, nima yopiq

### Bepul (Open / Community)

Maqsad: o‘rnatish oson, ishonch, “ishlaydi” degan signal.

1. **PostgreSQL**
2. **MySQL**
3. **REST API** (generic)
4. **Filesystem / S3** (Phase 0 oxirida)
5. Ixtiyoriy: **bitta** UZ connector “hook” sifatida (masalan faqat Click read-only) — muhokama qilinadi

Bepul qatlamda: cheksiz pipeline soni (self-host), asosiy quality check’lar, CLI.

### Tijorat (Pro / Business)

| Narsa | Nega pullik |
|-------|-------------|
| **Payme, Click, Uzum to‘lov** | Maxsus auth, API o‘zgarishlari, support yuklamasi |
| **1C** | Konfiguratsiya xilma-xilligi, OData/COM, support |
| **Didox** | E-invoicing, Soliq bog‘liqligi |
| **Soliq / MyGov** (agar API ochiq bo‘lsa) | Gov, barqarorlik, compliance |
| SLA, priority fix, private connector | Mijoz shartnomasi |
| Qo‘shimcha quality / notify / managed | Operatsion qiymat |

### AI zamonida “connector yopish” ishlaydimi?

**Ha, lekin boshqacha:**

- Oddiy REST (Bearer, pagination) — AI + `rest_api` wrapper yetarli → **bepul qoldiring**.
- Payme JSON-RPC, Click imzo, 1C metadata map, Didox hujjat oqimi — **domain bilim + test + monitoring** talab qiladi → pullik yoki “verified UZ” deb saqlang.
- Kodni yashirish emas; **barqarorlik + yangilanish + support** sotiladi. Kod ochiq bo‘lsa ham Pro = “biz ushlab turamiz, sizga javob beramiz”.

Airbyte darsi: connector’lar MIT, lekin Cloud/Enterprise va certified tier pullik. Biz ham: **UZ connector kodini ochiq qilish mumkin**, lekin binary/support/SLA va ba’zi connector’larni faqat litsenziya kaliti bilan yoqish — variant.

**Tavsiya (boshlang‘ich):**  
- Core wraps — to‘liq ochiq.  
- UZ connector’lar — ochiq kod (Apache 2.0), lekin Pro litsenziyasiz ishlamaydi yoki faqat limited mode (masalan oxirgi 7 kun).  
Yoki: UZ connector’lar Pro-only binary/plugin. Qaror keyinroq; strategiya “UZ = to‘lov” deb qoladi.

---

## 5. Qaysilarni yozamiz, qaysilarni yo‘q

### Yoziladi (tartib)

| Phase | Connector | Sabab | Qachon |
|-------|-----------|--------|--------|
| **0** | PostgreSQL, MySQL, REST API | dlt core, eng keng ishlatiladi, UI nomi aniq | Hozir (mavjud wrap’larni UI nomiga keltirish) |
| **0** | Filesystem / S3 | Dump va lake — deyarli har bir DE | Keyingi 1–2 sprint |
| **1** | **Click** | Eng keng to‘lov qamrovi | Birinchi UZ connector |
| **1** | **Payme** | Ikkinchi majburiy to‘lov; JSON-RPC = haqiqiy IP | Click’dan keyin |
| **1** | **1C** | Universal buxgalteriya | Parallel yoki to‘lovdan keyin |
| **2** | **Didox** | E-invoicing, Soliq ekosistema | 1C bilan bog‘liq mijozlar |
| **2** | Google Analytics / Sheets | Marketing + operatsiya | dlt verified wrap |
| **3** | Uzum, MoySklad, Soliq | Talab + API ochiqligi | Mijoz shartnomasi bilan |
| **3** | Facebook/Google Ads | Reklama | Talab bo‘lsa |

### Yozilmaydi (hozir)

- 50+ “katalog” SaaS (Asana, Freshdesk, Chess…) — Airbyte allaqachon bor, bizga load.
- Oddiy REST bilan ifodalanadigan va maxsus auth’siz source’lar — foydalanuvchi **REST API** connectoridan foydalansin.
- CDC/replication (Postgres logical) — murakkab; keyinroq yoki dlt `pg_replication` wrap.
- Bank core (Uzcard to‘g‘ridan-to‘g‘ri) — bank shartnomasi va compliance og‘ir.

### Connector yozish sababi (checklist)

Yangi connector faqat quyidagilardan **kamida 2 tasi** bo‘lsa:

1. Mijoz / pilot aniq so‘ragan  
2. UZ bozorida takrorlanuvchi (to‘lov, 1C, Didox…)  
3. dlt `rest_api` / `sql_database` bilan **to‘liq** ifodalanmaydi (maxsus auth yoki protocol)  
4. 3 oy ichida support qila olamiz (API hujjat, test account)

Aks holda — yozilmaydi.

---

## 6. Raqobatchilardan olingan dars

| Kim | Model | Dars |
|-----|--------|------|
| **Fivetran** | Yopiq, yuqori sifat, MAR narx | Sifat va SLA sotiladi; regional long-tail yo‘q → bizning joy |
| **Airbyte** | OSS + Cloud; certified vs community | Ko‘p connector = sifat xilma-xilligi; certified = ishonch |
| **dlt** | Core bepul, verified alohida repo, hub tijorat | Core’ni qayta yozma; hub’ga tushma |
| **PayTechUZ va mahalliy integrators** | Bitta lib’da Payme+Click+Uzum | UZ to‘lov birlashtirish qiymatli; lekin ular EL/warehouse emas — biz pipeline + destination |

**Chumoli pozitsiyasi:**  
“Oʻzbekiston uchun yengil Fivetran” — kam connector, lekin **ishlaydi**, UZ source’lar birinchi sinfda, self-host arzon, open core.

---

## 7. Amaliy roadmap (qisqa)

```
Phase 0 (hozir)
  □ UI nomlari: PostgreSQL, MySQL, REST API (sql_database ichki)
  □ Filesystem/S3 wrapper
  □ Har birining e2e test + dashboard’da ko‘rinishi
  □ Barqarorlik: xato xabarlari, retry, quality

Phase 1 (UZ moat)
  □ Click (birinchi UZ)
  □ Payme
  □ 1C (OData yoki fayl export — qaysi real mijozda bor)
  □ Open core chiziq: qaysi bepul / qaysi Pro — yozma qaror

Phase 2
  □ Didox
  □ Google Analytics / Sheets (dlt verified asosida)
  □ Mijoz so‘roviga qarab 1–2 ta

Phase 3
  □ Soliq / MoySklad / Uzum — faqat shartnoma yoki aniq talab
```

---

## 8. Xulosa

1. **Birinchi chiqaramiz:** dlt core — lekin **PostgreSQL / MySQL / REST API / Filesystem** deb.  
2. **Keyin:** Click → Payme → 1C → Didox (UZ moat).  
3. **Ko‘p yozmaymiz:** katalog uchun emas, mijoz + takrorlanuvchi talab uchun.  
4. **Pullik:** UZ connector’lar + SLA; generic REST/DB bepul.  
5. **AI:** oddiy REST arzonlashdi — biz domain + barqarorlik sotamiz.

Bu hujjat Claude dashboard ishidan mustaqil. Fundament barqaror bo‘lgach, Phase 0 nomlash va testlar bilan boshlash mumkin.
