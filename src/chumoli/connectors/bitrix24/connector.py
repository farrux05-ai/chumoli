"""
chumoli.connectors.bitrix24
=============================

Bitrix24 REST (inbound webhook yoki OAuth token).

Rasmiy:
  https://apidocs.bitrix24.com/settings/how-to-call-rest-api/authorization.html
  https://apidocs.bitrix24.com/api-reference/crm/deals/crm-deal-list.html

Webhook URL:
  https://{domain}.bitrix24.{ru|com|uz}/rest/{user_id}/{code}/

OAuth:
  portal = https://{domain}.bitrix24.uz  +  auth token (json `auth` maydoni)

List metodlar: sahifa 50 ta. Pagination `start` / javobdagi `next`.
CRM: result = [...].  tasks.task.list: result.tasks = [...].
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import dlt
import httpx

from chumoli import __version__
from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)
from chumoli.core.retry_policy import uz_api_retry

BITRIX_PAGE_SIZE = 50
TZ_TASHKENT = ZoneInfo("Asia/Tashkent")

# method, result extractor key (None = result is a list), API filter date field
RESOURCES: dict[str, tuple[str, str | None, str]] = {
    "deals": ("crm.deal.list", None, "DATE_MODIFY"),
    "leads": ("crm.lead.list", None, "DATE_MODIFY"),
    "contacts": ("crm.contact.list", None, "DATE_MODIFY"),
    "tasks": ("tasks.task.list", "tasks", "CHANGED_DATE"),
}

RESOURCE_PRIMARY_KEY: dict[str, str] = {
    "deals": "ID",
    "leads": "ID",
    "contacts": "ID",
    "tasks": "id",
}

# Cursor path = JSON response dagi maydon (filter maydonidan farq qilishi mumkin:
# tasks filter CHANGED_DATE, response esa changedDate).
RESOURCE_CURSOR_FIELD: dict[str, str] = {
    "deals": "DATE_MODIFY",
    "leads": "DATE_MODIFY",
    "contacts": "DATE_MODIFY",
    "tasks": "changedDate",
}

MANIFEST = ConnectorManifest(
    key="bitrix24",
    label="Bitrix24",
    category=ConnectorCategory.UZ_ERP,
    description="Bitrix24 REST — deal, lead, contact, task (webhook yoki OAuth)",
    dlt_source_factory="chumoli.connectors.bitrix24.connector.Bitrix24Connector",
    fields=[
        FieldSpec(
            key="webhook_url",
            label="Webhook yoki portal URL",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
            placeholder="https://company.bitrix24.uz/rest/1/xxxxx/",
            help_text=(
                "Inbound webhook (token URL ichida) yoki portal "
                "(https://company.bitrix24.uz) — u holda OAuth token ham kerak."
            ),
        ),
        FieldSpec(
            key="oauth_token",
            label="OAuth token (ixtiyoriy)",
            type=FieldType.PASSWORD,
            required=False,
            secret=True,
            help_text="Webhook ishlatsangiz bo'sh qoldiring. Portal URL uchun majburiy.",
        ),
        FieldSpec(
            key="resources",
            label="Resurs",
            type=FieldType.SELECT,
            required=True,
            default="all",
            options=[
                SelectOption(value="all", label="Hammasi"),
                SelectOption(value="deals", label="Deal (crm.deal.list)"),
                SelectOption(value="leads", label="Lead (crm.lead.list)"),
                SelectOption(value="contacts", label="Contact (crm.contact.list)"),
                SelectOption(value="tasks", label="Task (tasks.task.list)"),
            ],
        ),
        FieldSpec(
            key="from_days_ago",
            label="Necha kun oldin (default 7)",
            type=FieldType.NUMBER,
            required=False,
            default="7",
            help_text=(
                "Faqat birinchi run (yoki state tozalanganda) uchun pastki chegarа. "
                "Keyingi runlar oxirgi DATE_MODIFY / changedDate cursoridan davom etadi."
            ),
        ),
    ],
)


def parse_resources(raw: str | None) -> list[str]:
    value = (raw or "all").strip().lower()
    if value == "all":
        return list(RESOURCES)
    if value not in RESOURCES:
        raise ValueError(f"Noma'lum Bitrix24 resursi: {raw}")
    return [value]


def since_date(from_days_ago: int) -> str:
    days = max(0, int(from_days_ago))
    start = datetime.now(TZ_TASHKENT).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days)
    return start.strftime("%Y-%m-%d")


def normalize_webhook_url(url: str) -> str:
    """Trailing method.json ni olib tashlab, / bilan tugaydigan webhook/portal qaytaradi."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("Bitrix24 webhook/portal URL bo'sh")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Bitrix24 URL https://... bo'lishi kerak")
    path = parsed.path or "/"
    segments = [s for s in path.split("/") if s]
    # .../crm.deal.list.json yoki .../crm.deal.list — oxirgi segment metod
    if segments and "." in segments[-1]:
        last = segments[-1]
        if last.endswith(".json"):
            last = last[: -len(".json")]
        if last in {spec[0] for spec in RESOURCES.values()}:
            segments = segments[:-1]
    path = "/" + "/".join(segments)
    if path != "/":
        path += "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def is_webhook_url(url: str) -> bool:
    """https://host/rest/{userId}/{code}/ — inbound webhook."""
    parsed = urlparse(url)
    parts = [s for s in (parsed.path or "").split("/") if s]
    return len(parts) >= 3 and parts[0] == "rest"


def method_url(base: str, method: str) -> str:
    return f"{base.rstrip('/')}/{method}.json"


def extract_items(payload: Any, nested_key: str | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if nested_key:
        if isinstance(result, dict):
            items = result.get(nested_key) or result.get("items") or []
        else:
            items = []
    else:
        items = result if isinstance(result, list) else []
        if not items and isinstance(result, dict):
            items = result.get("items") or []
    return [x for x in items if isinstance(x, dict)]


@uz_api_retry
def _post_json(client: httpx.Client, url: str, body: dict[str, Any]) -> dict[str, Any]:
    resp = client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Bitrix24 kutilmagan javob")
    if data.get("error"):
        desc = data.get("error_description") or data.get("error")
        raise ValueError(f"Bitrix24 API [{data.get('error')}]: {desc}")
    return data


def _paginate(
    client: httpx.Client,
    url: str,
    body: dict[str, Any],
    nested_key: str | None,
) -> Iterator[dict[str, Any]]:
    start = 0
    while True:
        page_body = dict(body)
        page_body["start"] = start
        data = _post_json(client, url, page_body)
        items = extract_items(data, nested_key)
        if not items:
            break
        yield from items
        nxt = data.get("next")
        if nxt is None:
            if len(items) < BITRIX_PAGE_SIZE:
                break
            next_start = start + BITRIX_PAGE_SIZE
        else:
            next_start = int(nxt)
        # `next` 0 yoki oldinga siljimasa — progress yo'q, cheksiz loop'ni to'xtatamiz
        if next_start <= start:
            break
        start = next_start


def _make_resource(
    name: str,
    method: str,
    nested_key: str | None,
    date_field: str,
    base: str,
    oauth_token: str | None,
    since: str,
):
    pk = RESOURCE_PRIMARY_KEY[name]
    url = method_url(base, method)
    cursor_field = RESOURCE_CURSOR_FIELD[name]

    @dlt.resource(name=name, write_disposition="merge", primary_key=pk)
    def _resource(
        modified: dlt.sources.incremental[str] = dlt.sources.incremental(
            cursor_field,
            initial_value=since,
            last_value_func=max,
            # Ba'zi yozuvlarda cursor null bo'lishi mumkin — drop qilmaslik
            on_cursor_value_missing="include",
        ),
    ) -> Iterator[dict[str, Any]]:
        # start_value: birinchi run = since (from_days_ago); keyin = oxirgi cursor
        body: dict[str, Any] = {
            "filter": {f">={date_field}": modified.start_value},
            "order": {date_field: "ASC"},
        }
        if oauth_token:
            body["auth"] = oauth_token
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"Chumoli/{__version__} (+https://github.com/farrux05-ai/chumoli)",
        }
        with httpx.Client(timeout=60.0, headers=headers) as client:
            yield from _paginate(client, url, body, nested_key)

    return _resource


@dlt.source(name="bitrix24")
def bitrix24_source(
    webhook_url: str,
    oauth_token: str | None,
    resources: list[str],
    from_days_ago: int,
) -> Any:
    base = normalize_webhook_url(webhook_url)
    token = (oauth_token or "").strip() or None
    if not is_webhook_url(base):
        if not token:
            raise ValueError(
                "Portal URL uchun OAuth token kerak. Yoki inbound webhook URL qo'ying "
                "(https://portal.bitrix24.uz/rest/1/xxxxx/)."
            )
        # OAuth chaqiruv: https://portal/rest/method.json + auth
        if not base.rstrip("/").endswith("/rest"):
            base = base.rstrip("/") + "/rest/"
    since = since_date(from_days_ago)
    out = []
    for name in resources:
        method, nested, date_field = RESOURCES[name]
        out.append(_make_resource(name, method, nested, date_field, base, token, since))
    return out

class Bitrix24Connector:
    """Bitrix24 REST — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        webhook_url = secrets.get("webhook_url") or str(params.get("webhook_url") or "")
        oauth_token = secrets.get("oauth_token") or None
        resources = parse_resources(str(params.get("resources") or "all"))
        days = int(params.get("from_days_ago") or 7)
        return bitrix24_source(
            webhook_url=webhook_url,
            oauth_token=oauth_token,
            resources=resources,
            from_days_ago=days,
        )
