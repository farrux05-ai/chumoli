# Chumoli — API / Connector Maintenance Strategy

> **Holat (2026-09-26):** bu **taklif** — `connectors_monitor/` va
> `.github/workflows/connector-monitor.yml` hali repoda yo'q. Hujjat kelajakdagi
> monitoring rejasini saqlaydi.

**Muammo:** tashqi API o‘zgarsa connector “jim” buziladi.  
**Maqsad:** oyiga (yoki haftada) avtomatik scan → o‘zgarish topilsa GitHub **issue** ochilsin → siz tuzatasiz.  
**Sana:** 2026-09-18

---

## 1. Nima uchun bu eng muhim

| Fakt | Oqibat |
|------|--------|
| Siz API’ni boshqarmaysiz | Payme/Click/1C/Didox o‘z vaqtida deprecation chiqaradi |
| Hujjat kech yangilanadi yoki umuman yo‘q | Faqat “changelog o‘qish” yetarli emas |
| AI oddiy REST’ni yozadi | Lekin **monitoring + regression test** sizda qoladi — bu Pro qiymati |
| Fivetran/Airbyte | O‘z jamoasi connector’larni ushlab turadi; sizda jamoa kichik → avtomatlashtirish shart |

**Qoida:** har bir UZ connector uchun kamida bitta **avtomatik signal** bo‘lishi kerak. Signal = issue, chatga xabar emas.

---

## 2. Uch qatlamli himoya (tavsiya)

```
┌─────────────────────────────────────────────────────────┐
│  A. Contract / schema monitor (haftalik yoki oylik)      │
│     OpenAPI bor → oasdiff                                │
│     OpenAPI yo‘q → response snapshot + shape hash        │
├─────────────────────────────────────────────────────────┤
│  B. Live smoke test (har kecha yoki har 3 kunda)         │
│     Minimal authenticated request → status + schema      │
│     Muvaffaqiyatsiz → issue yoki failed check            │
├─────────────────────────────────────────────────────────┤
│  C. Docs / changelog watch (ixtiyoriy)                   │
│     Hujjat URL yoki blog RSS o‘zgarsa → issue            │
└─────────────────────────────────────────────────────────┘
```

A + B majburiy. C — qo‘shimcha erta ogohlantirish.

---

## 3. Qaysi usul qaysi connector uchun

| Connector turi | OpenAPI? | Asosiy usul | Qo‘shimcha |
|----------------|----------|-------------|------------|
| **PostgreSQL / MySQL** | Yo‘q (SQL) | dlt + o‘z e2e testlari | Schema drift destination’da quality check |
| **REST API (generic)** | Ba’zan | Foydalanuvchi o‘zi javobgar | Biz faqat wrapper’ni test qilamiz |
| **Payme** | Odatda yo‘q | Smoke + JSON-RPC method list snapshot | Hujjat sahifasi watch |
| **Click** | Odatda yo‘q | Smoke + imzo/param maydonlari snapshot | Merchant kabinet hujjatlari |
| **1C** | OData metadata | `$metadata` XML/JSON diff | Konfiguratsiya xilma-xil — test account |
| **Didox** | Noma’lum | Smoke + asosiy endpoint response shape | |
| **dlt verified** (GA, Sheets…) | Ko‘pincha bor | Upstream dlt + o‘z thin-wrap test | Kamroq yuklama |

**Muhim:** Payme/Click kabi UZ API’larda OpenAPI deyarli yo‘q. Shuning uchun faqat `oasdiff` ga tayanmang — **live response snapshot** asosiy qurol.

---

## 4. Amaliy arxitektura (GitHub Actions + repo)

### Papka tuzilmasi (taklif)

```
chumoli/
  connectors_monitor/
    baselines/           # oxirgi muvaffaqiyatli snapshot’lar
      payme/
        methods.json     # JSON-RPC method nomlari / sample response keys
        last_ok.json
      click/
        ...
      one_c/
        metadata_hash.txt
    configs/
      monitors.yaml      # qaysi connector, URL, auth secret nomi, chastota
    scripts/
      scan_openapi.py    # OpenAPI bo‘lsa
      scan_snapshot.py   # response shape
      open_issue.py      # gh api orqali issue
  .github/workflows/
    connector-monitor.yml
```

### `monitors.yaml` misol

```yaml
monitors:
  - id: payme
    type: snapshot
    # haqiqiy endpoint’lar secret orqali
    schedule: weekly   # yoki monthly
    baseline: baselines/payme/last_ok.json
    on_change: open_issue
    labels: [connector, payme, maintenance]

  - id: click
    type: snapshot
    schedule: weekly
    baseline: baselines/click/last_ok.json
    on_change: open_issue
    labels: [connector, click, maintenance]

  - id: postgres
    type: e2e_test
    schedule: daily
    command: pytest tests/test_e2e_sql_database_to_duckdb.py -q
    on_fail: open_issue
    labels: [connector, postgres, maintenance]
```

### Workflow g‘oyasi

```yaml
# .github/workflows/connector-monitor.yml
name: Connector API monitor
on:
  schedule:
    - cron: "0 6 * * 1"   # har dushanba 06:00 UTC (~11:00 Toshkent)
  workflow_dispatch:        # qo‘lda ham ishga tushirish

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]" httpx pyyaml
      - name: Run monitors
        env:
          PAYME_TEST_KEY: ${{ secrets.PAYME_TEST_KEY }}
          CLICK_TEST_KEY: ${{ secrets.CLICK_TEST_KEY }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python connectors_monitor/scripts/run_all.py
```

`run_all.py` mantiq:

1. Har bir monitor uchun so‘rov yuboradi (yoki OpenAPI yuklaydi).  
2. Natijani baseline bilan solishtiradi (field set, types, status code).  
3. Farq yoki xato bo‘lsa:
   - mavjud ochiq issue bormi (`label:connector` + `payme`) — takrorlamaslik;
   - yo‘q bo‘lsa — **yangi issue** ochadi:

```text
Title: [monitor] Payme API drift detected — 2026-09-18
Body:
  - Removed keys: ...
  - Type changes: ...
  - HTTP status: ...
  - Baseline: baselines/payme/last_ok.json
  - Action: review connector + update tests
Labels: connector, payme, maintenance, auto
```

4. Ixtiyoriy: farq “xavfsiz” (faqat yangi optional field) bo‘lsa — baseline’ni yangilab commit qiladi; breaking bo‘lsa — faqat issue.

---

## 5. Snapshot qanday ishlaydi (OpenAPI yo‘q holat)

```text
1. Test credential bilan 1–2 ta “read” so‘rov (masalan GetStatement, balance)
2. Response’dan faqat STRUKTURA olinadi:
   - top-level keys
   - nested key paths (depth 2–3)
   - oddiy type map: string | number | bool | null | array | object
3. Qiymatlar SAQLANMAYDI (PII/secret chiqmasin)
4. Hash yoki sorted JSON solishtiriladi
5. Farq → issue
```

**Breaking deb hisoblash:**

- majburiy deb o‘ylangan key yo‘qoldi  
- type o‘zgardi (number → string)  
- HTTP 401/403/404/5xx (auth yoki endpoint o‘chgan)  
- JSON-RPC method “method not found”

**Breaking emas (baseline yangilash mumkin):**

- yangi optional field  
- yangi enum qiymat (agar connector ignore qilsa)

---

## 6. OpenAPI bor bo‘lsa

Vositalar (bepul, self-host):

| Tool | Vazifa |
|------|--------|
| **oasdiff** | `oasdiff breaking baseline.yaml live.yaml` — exit code + matn |
| **openapi-diff** | PR/changelog uchun |
| **Spectral** | Spec sifatini lint qilish (ixtiyoriy) |

Oqim:

```bash
curl -sS "$OPENAPI_URL" -o /tmp/live.yaml
oasdiff breaking baselines/foo/openapi.yaml /tmp/live.yaml --fail-on ERR
# exit != 0 → open_issue.py
```

Agar provider OpenAPI’ni faqat login orqasida bersa — secret + bir xil oqim.

---

## 7. Chastota tavsiyasi

| Qatlam | Chastota | Sabab |
|--------|----------|--------|
| Smoke (B) | Har 1–3 kun | Tez “o‘lik” API’ni ushlash |
| Snapshot / OpenAPI (A) | Haftalik | Drift sekin bo‘lishi mumkin |
| To‘liq e2e pytest | PR da + haftalik | Regression |
| Docs HTML watch (C) | Oylik yoki haftalik | Erta signal, shovqinli bo‘lishi mumkin |

Boshida: **haftalik bitta workflow** yetarli. Keyin smoke’ni ajratib kunlik qilish mumkin.

---

## 8. Issue’ni kim yopadi

1. Monitor issue ochadi (`auto` label).  
2. Siz yoki men (chat/task) connector kodini yangilaysiz.  
3. Test o‘tadi → baseline yangilanadi (qo‘lda yoki “accept baseline” workflow).  
4. Issue yopiladi.

**Takroriy issue ochilmasin:** bir xil `monitor_id` + ochiq issue bo‘lsa — comment qo‘shiladi, yangi issue emas.

---

## 9. Secret va xavfsizlik

- Test merchant / sandbox kalitlari — faqat GitHub Actions secrets.  
- Snapshot’da **qiymat yozilmasin** — faqat schema.  
- Production merchant kaliti monitor’da ishlatilmasin.  
- Rate limit: kuniga 1–2 so‘rov connector uchun.

---

## 10. AI / men bilan bog‘lanish

Variantlar:

1. **Issue ochiladi** → siz chatda “Payme issue #12 ni tuzat” deysiz → men kod + PR/push.  
2. **Automation** (Grok Automations): har dushanba “chumoli open maintenance issues’ni ko‘r” deb eslatma.  
3. Keyinroq: issue body’dan avtomatik branch + draft PR (murakkabroq; hozir shart emas).

Hozir eng barqaror: **Actions → issue → odam/AI tuzatadi**.

---

## 11. Nima qilmaslik

| Yomon yondashuv | Nega |
|-----------------|------|
| Faqat vendor changelog o‘qish | UZ API’lar ko‘pincha yozmaydi |
| Faqat OpenAPI (Payme/Click’da yo‘q) | Ko‘p signal yo‘qoladi |
| Har soat so‘rov | Rate limit, ban, shovqin |
| Production credentials monitor’da | Xavf |
| 50 ta connector bir xil chuqurlikda | Sifat yo‘qoladi — faqat **sizdagi** connector’lar |

---

## 12. Minimal MVP (1–2 kun ish)

1. `connectors_monitor/configs/monitors.yaml` — 2–3 ta connector.  
2. `scan_snapshot.py` — bitta generic shape-diff.  
3. `open_issue.py` — `gh issue create` yoki REST API.  
4. `.github/workflows/connector-monitor.yml` — cron + `workflow_dispatch`.  
5. Sandbox secret’lar.  
6. Bir marta qo‘lda ishga tushirib, sun’iy farq bilan issue ochilishini tekshirish.

Keyin Click/Payme qo‘shilganda monitor qatori qo‘shiladi — yangi infra kerak emas.

---

## 13. Xulosa

- **Maintenance = avtomatik signal + tez tuzatish**, 500 connector emas.  
- UZ API’lar uchun: **live snapshot + smoke**, OpenAPI ixtiyoriy.  
- GitHub Actions (haftalik) → **issue** → siz/men tuzatamiz.  
- Bu open core Pro qiymatining bir qismi: “biz ushlab turamiz”.

Keyingi qadam: MVP workflow’ni `chumoli` repoga yozish (secret’larsiz skeleton) yoki avval qaysi 2 connector’dan boshlashni tanlash.
