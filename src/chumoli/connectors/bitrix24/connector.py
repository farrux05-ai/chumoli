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

# method, result extractor key (None = result is a list), date filter field
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

# Explicit column hints — kalitlar Bitrix JSON dagi ASLI nomlar (dlt o'zi normalize qiladi).
# CRM list: UPPERCASE. tasks.task.list: camelCase. Nested creator/responsible hint
# qilinmaydi — data flatten qilganda collision chiqardi (snake_case hint × camelCase data).
# UF_* portal custom — hint yo'q (data kelganda dlt qo'shadi).
_T = {"data_type": "text"}
_D = {"data_type": "double"}
_I = {"data_type": "bigint"}
_TS = {"data_type": "timestamp"}

_CRM_UTM = {
    "UTM_SOURCE": _T,
    "UTM_MEDIUM": _T,
    "UTM_CAMPAIGN": _T,
    "UTM_CONTENT": _T,
    "UTM_TERM": _T,
}

_CRM_ADDRESS = {
    "ADDRESS": _T,
    "ADDRESS_2": _T,
    "ADDRESS_CITY": _T,
    "ADDRESS_POSTAL_CODE": _T,
    "ADDRESS_REGION": _T,
    "ADDRESS_PROVINCE": _T,
    "ADDRESS_COUNTRY": _T,
    "ADDRESS_COUNTRY_CODE": _T,
    "ADDRESS_LOC_ADDR_ID": _T,
}

RESOURCE_COLUMNS: dict[str, dict[str, dict[str, Any]]] = {
    "deals": {
        "ID": {**_T, "nullable": False},
        "TITLE": _T,
        "TYPE_ID": _T,
        "CATEGORY_ID": _T,
        "STAGE_ID": _T,
        "STAGE_SEMANTIC_ID": _T,
        "IS_NEW": _T,
        "IS_RECURRING": _T,
        "IS_RETURN_CUSTOMER": _T,
        "IS_REPEATED_APPROACH": _T,
        "PROBABILITY": _I,
        "CURRENCY_ID": _T,
        "OPPORTUNITY": _D,
        "IS_MANUAL_OPPORTUNITY": _T,
        "TAX_VALUE": _D,
        "COMPANY_ID": _T,
        "CONTACT_ID": _T,
        "QUOTE_ID": _T,
        "BEGINDATE": _TS,
        "CLOSEDATE": _TS,
        "OPENED": _T,
        "CLOSED": _T,
        "COMMENTS": _T,
        "ASSIGNED_BY_ID": _T,
        "CREATED_BY_ID": _T,
        "MODIFY_BY_ID": _T,
        "DATE_CREATE": _TS,
        "DATE_MODIFY": _TS,
        "SOURCE_ID": _T,
        "SOURCE_DESCRIPTION": _T,
        "LEAD_ID": _T,
        "ADDITIONAL_INFO": _T,
        "LOCATION_ID": _T,
        "ORIGINATOR_ID": _T,
        "ORIGIN_ID": _T,
        "LAST_COMMUNICATION_TIME": _TS,
        "REPEAT_SALE_SEGMENT_ID": _T,
        **_CRM_UTM,
    },
    "leads": {
        "ID": {**_T, "nullable": False},
        "TITLE": _T,
        "HONORIFIC": _T,
        "NAME": _T,
        "SECOND_NAME": _T,
        "LAST_NAME": _T,
        "BIRTHDATE": _TS,
        "COMPANY_TITLE": _T,
        "COMPANY_ID": _T,
        "SOURCE_ID": _T,
        "SOURCE_DESCRIPTION": _T,
        "STATUS_ID": _T,
        "STATUS_DESCRIPTION": _T,
        "STATUS_SEMANTIC_ID": _T,
        "POST": _T,
        "COMMENTS": _T,
        "CURRENCY_ID": _T,
        "OPPORTUNITY": _D,
        "IS_MANUAL_OPPORTUNITY": _T,
        "OPENED": _T,
        "ASSIGNED_BY_ID": _T,
        "CREATED_BY_ID": _T,
        "MODIFY_BY_ID": _T,
        "DATE_CREATE": _TS,
        "DATE_MODIFY": _TS,
        "DATE_CLOSED": _TS,
        "ORIGINATOR_ID": _T,
        "ORIGIN_ID": _T,
        "LAST_COMMUNICATION_TIME": _TS,
        **_CRM_ADDRESS,
        **_CRM_UTM,
    },
    "contacts": {
        "ID": {**_T, "nullable": False},
        "HONORIFIC": _T,
        "NAME": _T,
        "SECOND_NAME": _T,
        "LAST_NAME": _T,
        "PHOTO": _T,
        "BIRTHDATE": _TS,
        "TYPE_ID": _T,
        "SOURCE_ID": _T,
        "SOURCE_DESCRIPTION": _T,
        "POST": _T,
        "COMMENTS": _T,
        "OPENED": _T,
        "EXPORT": _T,
        "HAS_PHONE": _T,
        "HAS_EMAIL": _T,
        "ASSIGNED_BY_ID": _T,
        "CREATED_BY_ID": _T,
        "MODIFY_BY_ID": _T,
        "DATE_CREATE": _TS,
        "DATE_MODIFY": _TS,
        "COMPANY_ID": _T,
        "ORIGINATOR_ID": _T,
        "ORIGIN_ID": _T,
        "ORIGIN_VERSION": _T,
        "LAST_COMMUNICATION_TIME": _TS,
        **_CRM_ADDRESS,
        **_CRM_UTM,
    },
    # tasks.task.list returns camelCase keys in JSON
    "tasks": {
        "id": {**_T, "nullable": False},
        "parentId": _T,
        "title": _T,
        "description": _T,
        "mark": _T,
        "priority": _T,
        "status": _T,
        "multitask": _T,
        "notViewed": _T,
        "replicate": _T,
        "groupId": _T,
        "stageId": _T,
        "createdBy": _T,
        "createdDate": _TS,
        "responsibleId": _T,
        "changedBy": _T,
        "changedDate": _TS,
        "statusChangedBy": _T,
        "statusChangedDate": _TS,
        "closedBy": _T,
        "closedDate": _TS,
        "activityDate": _TS,
        "dateStart": _TS,
        "deadline": _TS,
        "startDatePlan": _TS,
        "endDatePlan": _TS,
        "guid": _T,
        "xmlId": _T,
        "commentsCount": _I,
        "serviceCommentsCount": _I,
        "allowChangeDeadline": _T,
        "allowTimeTracking": _T,
        "taskControl": _T,
        "addInReport": _T,
        "forkedByTemplateId": _T,
        "timeEstimate": _I,
        "timeSpentInLogs": _I,
        "matchWorkTime": _T,
        "forumTopicId": _T,
        "forumId": _T,
        "siteId": _T,
        "subordinate": _T,
        "exchangeModified": _TS,
        "exchangeId": _T,
        "outlookVersion": _I,
        "viewedDate": _TS,
        "sorting": _D,
        "durationPlan": _I,
        "durationFact": _I,
        "durationType": _T,
        "isMuted": _T,
        "isPinned": _T,
        "isPinnedInGroup": _T,
        "flowId": _T,
        "sprintId": _T,
        "backlogId": _T,
    },
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
    columns = RESOURCE_COLUMNS.get(name)

    @dlt.resource(
        name=name,
        write_disposition="merge",
        primary_key=pk,
        columns=columns,
    )
    def _resource() -> Iterator[dict[str, Any]]:
        body: dict[str, Any] = {
            "filter": {f">={date_field}": since},
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
