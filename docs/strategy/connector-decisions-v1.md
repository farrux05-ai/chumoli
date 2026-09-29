# Chumoli — Connector Decisions v1

**Sana:** 2026-09-29 (yangilandi)  
**Maqsad:** V1 uchun qaysi connectorlar chiqadi, qaysilari experimental, qaysilari yozilmaydi — va nima uchun.  
**Asosiy qoida (qat’iy):**  
Connector **“Tayyor”** deb faqat quyidagi shartlar bajarilganda chiqariladi:
1. Sandbox, bepul tier yoki local test mumkin
2. Hujjat ochiq
3. UZ bozorida haqiqiy demand bor
4. e2e test (real yoki sandbox) o‘tgan

Agar faqat live credential bilan ishlasa → `experimental` (skeleton + ochiq ogohlantirish).

Kodda maturity: **stable** = Tayyor, **beta** = Experimental (mavjud UI badge).

---

## V1 da chiqadiganlar (Tayyor)

Faqat to‘liq test qilinadiganlar. Bular V1 release da “Tayyor” holatda bo‘ladi.

| Key | Label | Nima uchun V1 | Holat |
|-----|-------|---------------|-------|
| `rest_api` | REST API | dlt core, stabil | ✅ Tayyor |
| `sql_database` | SQL Database | dlt core | ✅ Tayyor |
| `postgresql` | PostgreSQL | dlt core wrap | ✅ Tayyor |
| `mysql` | MySQL | dlt core wrap | ✅ Tayyor |
| `synthetic_volume` | Volume demo | Test/demo uchun | ✅ Tayyor |
| `filesystem_s3` | Filesystem / S3 | Local + S3, credential tashqi emas yoki AWS | ✅ Prod (0.1.2) |
| `moysklad` | MoySklad | Bepul tier = sandbox, REST JSON, CIS + UZ | ✅ Prod (0.1.2) |
| `bitrix24` | Bitrix24 | Webhook/OAuth, o‘zi test account ochish mumkin, UZ da keng | ✅ Prod (0.1.2) |

**Jami V1 Tayyor:** 8 ta

> **0.1.2 holati:** kodda `maturity: stable` — `rest_api`, `sql_database`,
> `postgresql`, `mysql`, `filesystem_s3`, `synthetic_volume`, `bitrix24`,
> `moysklad`. Prod deb faqat shular e’lon qilinadi; fayldagi qolgan yozuvlar
> dastlabki reja.

---

## Experimental (V1 da kod bor, lekin “Tayyor” emas)

Skeleton yoziladi, `maturity: beta`.  
UI da ochiq yoziladi: “Sandbox yo‘q — o‘zing credential berib sinab ko‘ring. e2e kafolatlanmagan.”

| Key | Label | Sabab | Holat |
|-----|-------|-------|-------|
| `click_uz` | Click | Sandbox yo‘q, live only | Experimental (mavjud kod saqlanadi) |
| `uzum_market` | Uzum Market / Seller | Credential-gated, live only | Experimental (mavjud kod saqlanadi) |
| `didox` | Didox | Sandbox yo‘q | Experimental (mavjud kod saqlanadi) |
| `payme_uz` | Payme | Sandbox bor, lekin e2e hali tasdiqlanmagan | Beta (kod bor) |
| `facebook_ads` | Meta Ads (Facebook) | dlt Community source, sandbox yo‘q, real token kerak | Experimental (yozildi) |
| `uzum_bank` | Uzum Bank | Self-service sandbox yo‘q, account manager kerak | Skeleton + experimental — **hali yozilmagan** |

**Qoida:** Experimental connectorlar V1 katalogda ko‘rinadi, lekin default “Tayyor” ro‘yxatida emas. Pilot mijoz credential bersa — tezda Tayyor ga o‘tkaziladi.

---

## V1.1 yoki keyinroq (hozir yozilmaydi)

| Key | Label | Sabab |
|-----|-------|-------|
| `telegram_bot` | Telegram Bot | Demand bor, lekin incremental/polling murakkab; V1.1 |
| `1c_odata` / `onec_odata` | 1C Enterprise OData | Har kompaniyada konfiguratsiya boshqacha, support og‘ir |

---

## Hech qachon yozilmaydi (yoki juda kech)

| Connector | Sabab |
|-----------|-------|
| `soliq_uz` | Public API yo‘q |
| `mygov` | API yo‘q, shartnoma kerak |
| `uzcard` / `humo` | Bank shartnomasi + compliance |
| `google_analytics` | dlt verified source bor — wrap qilish mumkin, lekin global, UZ moat emas |
| `shopify` | UZ da demand past |
| `stripe` | UZ da cheklangan |

---

## V1 Final ro‘yxat (chiqariladigan)

```
Tayyor (8):
─────────────────────────────
rest_api
sql_database
postgresql
mysql
synthetic_volume
filesystem_s3      ← prod (0.1.2)
moysklad           ← prod (0.1.2)
bitrix24           ← prod (0.1.2)

Experimental (6):
─────────────────────────────
click_uz
payme_uz
uzum_market
didox
facebook_ads       ← yozildi (Meta Marketing API, beta)
uzum_bank          ← skeleton (hali yo'q)
```

---

## Yangi connectorlar (implementatsiya)

### 1. `filesystem_s3`
- dlt `readers` thin wrap (`read_csv_duckdb` / `read_parquet` / `read_jsonl`)
- Manifest: `path_or_url`, `file_format` (csv/parquet/jsonl), `glob_pattern`, ixtiyoriy AWS kalitlar
- Lokal e2e: JSONL → DuckDB

### 2. `moysklad`
- Base: `https://api.moysklad.ru/api/remap/1.2`
- Auth: Bearer yoki Basic (`login:parol` token maydonida)
- Resurslar: customerorder, demand, invoiceout, product, stock, retaildemand
- Header: `Accept-Encoding: gzip` (boshqasi 415)
- Pagination: limit/offset, `{meta, rows}`
- Manifest: `token`, `resources`, `from_days_ago`
- e2e: lokal mock HTTP → DuckDB

### 3. `bitrix24`
- REST: inbound webhook `https://{domain}.bitrix24.{ru|com|uz}/rest/{user}/{code}/`
  yoki portal + OAuth token
- Resurslar: crm.deal.list, crm.lead.list, crm.contact.list, tasks.task.list
- Pagination: `start` / `next`, sahifa 50
- e2e: lokal mock webhook → DuckDB

---

## Connector yozish checklist (har biri uchun)

```
[x] src/chumoli/connectors/<key>/__init__.py
[x] src/chumoli/connectors/<key>/connector.py   (MANIFEST + class)
[x] connectors/__init__.py ga qo‘shish
[x] tests/test_<key>.py                        (manifest + build, network yo‘q)
[x] tests/test_e2e_<key>_to_duckdb.py          (real/sandbox load)
[x] docs/skills/write-connector.md qoidalariga mos
[x] maturity: stable (Tayyor) yoki beta (experimental)
[x] pytest tests/ -q — yashil (0.1.2: 236 passed)
```

---

## Qarorlar asosi (qisqa)

- **Sandbox / bepul / local bor** → Tayyor
- **Istisno:** Payme’da sandbox bor, ammo e2e tasdiqlanmagani uchun 0.1.2 da beta qoldirildi
- **Faqat live credential** → Experimental (kod bor, kafolat yo‘q)
- **API yo‘q yoki yopiq** → Yozilmaydi
- **Global dlt source** → Faqat UZ moat bo‘lsa wrap, aks holda yo‘naltirish

Bu hujjat connector qo‘shilgan/olib tashlangan yoki status o‘zgargan sari yangilanadi.
