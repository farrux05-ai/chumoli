"""
chumoli.connectors.facebook_ads
================================

Meta Marketing API (Facebook / Instagram Ads).

dlt verified source: https://dlthub.com/docs/dlt-ecosystem/verified-sources/facebook_ads
GitHub: https://github.com/dlt-hub/verified-sources/tree/master/sources/facebook_ads

Eslatma: dlt da Community source (bir marta test qilingan, regular CI yo'q).
Sandbox yo'q — real Meta Business access_token + account_id kerak.
Shuning uchun maturity=beta.

Auth: access_token (query param yoki Bearer)
Base: https://graph.facebook.com/v21.0
Asosiy resurslar: campaigns, adsets, ads

Rasmiy Marketing API: https://developers.facebook.com/docs/marketing-api
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

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
from chumoli.core.retry_policy import is_transient_status_code, uz_api_retry

GRAPH_BASE = "https://graph.facebook.com/v21.0"
PAGE_SIZE = 100

# Default fields aligned with dlt verified source defaults
DEFAULT_CAMPAIGN_FIELDS = (
    "id,name,status,effective_status,objective,created_time,updated_time,"
    "start_time,stop_time,daily_budget,lifetime_budget"
)
DEFAULT_ADSET_FIELDS = (
    "id,name,status,effective_status,campaign_id,created_time,updated_time,"
    "start_time,end_time,daily_budget,lifetime_budget,optimization_goal,"
    "billing_event,bid_amount"
)
DEFAULT_AD_FIELDS = (
    "id,name,status,effective_status,adset_id,campaign_id,created_time,"
    "updated_time,creative,targeting"
)

RESOURCE_PATHS: dict[str, str] = {
    "campaigns": "campaigns",
    "adsets": "adsets",
    "ads": "ads",
}

RESOURCE_FIELDS: dict[str, str] = {
    "campaigns": DEFAULT_CAMPAIGN_FIELDS,
    "adsets": DEFAULT_ADSET_FIELDS,
    "ads": DEFAULT_AD_FIELDS,
}


MANIFEST = ConnectorManifest(
    key="facebook_ads",
    label="Meta Ads (Facebook)",
    category=ConnectorCategory.UNIVERSAL,
    maturity="beta",
    description=(
        "Meta Marketing API — campaigns, adsets, ads (beta: real access_token kerak, "
        "sandbox yo'q; dlt Community source asosida)"
    ),
    dlt_source_factory="chumoli.connectors.facebook_ads.connector.FacebookAdsConnector",
    fields=[
        FieldSpec(
            key="account_id",
            label="Ad Account ID",
            type=FieldType.TEXT,
            required=True,
            placeholder="act_1234567890 yoki 1234567890",
            help_text=(
                "Ads Manager URL dagi act=... raqami. "
                "act_ prefiksi ixtiyoriy — avtomatik qo'shiladi."
            ),
        ),
        FieldSpec(
            key="access_token",
            label="Access Token",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
            help_text=(
                "Meta for Developers → Graph API Explorer yoki System User token. "
                "ads_read ruxsati kerak. Long-lived token tavsiya etiladi."
            ),
        ),
        FieldSpec(
            key="resources",
            label="Resurslar",
            type=FieldType.SELECT,
            required=True,
            default="all",
            options=[
                SelectOption(value="all", label="Hammasi (campaigns + adsets + ads)"),
                SelectOption(value="campaigns", label="Campaigns"),
                SelectOption(value="adsets", label="Ad sets"),
                SelectOption(value="ads", label="Ads"),
            ],
        ),
        FieldSpec(
            key="api_version",
            label="API versiya (ixtiyoriy)",
            type=FieldType.TEXT,
            required=False,
            default="v21.0",
            placeholder="v21.0",
            help_text="Default v21.0. Token qaysi versiya uchun berilgan bo'lsa, shuni yozing.",
        ),
    ],
)


def normalize_account_id(raw: str) -> str:
    """act_123 yoki 123 → act_123."""
    value = (raw or "").strip()
    if not value:
        raise ValueError("Meta Ad Account ID bo'sh")
    if value.lower().startswith("act_"):
        return value
    return f"act_{value}"


def parse_resources(raw: str | None) -> list[str]:
    value = (raw or "all").strip().lower()
    if value == "all":
        return list(RESOURCE_PATHS)
    if value not in RESOURCE_PATHS:
        raise ValueError(f"Noma'lum Meta Ads resursi: {raw}")
    return [value]


def _error_detail(resp: httpx.Response, data: Any) -> str:
    """Meta xato javobidan o'qiladigan xabar (JSON bo'lmasa — status + body)."""
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return (
            f"Meta API [{err.get('code', resp.status_code)}]: "
            f"{err.get('message', resp.text)}"
        )
    return f"Meta API [{resp.status_code}]: {(resp.text or '').strip()[:200]}"


@uz_api_retry
def _get_json(
    client: httpx.Client,
    path: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    resp = client.get(path, params=params)
    try:
        data: Any = resp.json()
    except ValueError:
        # HTML/plain-text xato sahifasi (masalan proxy'dan 502) — JSON yo'q
        data = None
    if not resp.is_success:
        message = _error_detail(resp, data)
        if is_transient_status_code(resp.status_code):
            # 429/5xx → HTTPStatusError: `uz_api_retry` qayta urinadi.
            # ValueError ko'tarilsa tenacity uni transient deb hisoblamaydi.
            raise httpx.HTTPStatusError(message, request=resp.request, response=resp)
        raise ValueError(message)
    if not isinstance(data, dict):
        raise ValueError("Meta API kutilmagan javob (object emas)")
    return data


def _paginate(
    client: httpx.Client,
    path: str,
    fields: str,
    access_token: str,
) -> Iterator[dict[str, Any]]:
    params: dict[str, Any] = {
        "access_token": access_token,
        "fields": fields,
        "limit": PAGE_SIZE,
    }
    previous_after: str | None = None
    while True:
        data = _get_json(client, path, params)
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict):
                yield row
        paging = data.get("paging") if isinstance(data.get("paging"), dict) else {}
        cursors = paging.get("cursors") if isinstance(paging.get("cursors"), dict) else {}
        after = cursors.get("after")
        # Kursor takrorlansa (yoki umuman bo'lmasa) — cheksiz loop himoyasi
        if not after or not paging.get("next") or after == previous_after:
            break
        previous_after = after
        params = {
            "access_token": access_token,
            "fields": fields,
            "limit": PAGE_SIZE,
            "after": after,
        }


def _client(base_url: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/") + "/",
        headers={
            "Accept": "application/json",
            "User-Agent": f"Chumoli/{__version__} (+https://github.com/farrux05-ai/chumoli)",
        },
        timeout=90.0,
    )


def _make_resource(
    name: str,
    account_id: str,
    access_token: str,
    base_url: str,
):
    path = f"{account_id}/{RESOURCE_PATHS[name]}"
    fields = RESOURCE_FIELDS[name]

    @dlt.resource(name=name, write_disposition="merge", primary_key="id")
    def _resource() -> Iterator[dict[str, Any]]:
        with _client(base_url) as client:
            yield from _paginate(client, path, fields, access_token)

    return _resource


@dlt.source(name="facebook_ads")
def facebook_ads_source(
    account_id: str,
    access_token: str,
    resources: list[str],
    api_version: str = "v21.0",
) -> Any:
    ver = (api_version or "v21.0").strip()
    if not ver.startswith("v"):
        ver = f"v{ver}"
    base_url = f"https://graph.facebook.com/{ver}"
    act = normalize_account_id(account_id)
    out = []
    for name in resources:
        out.append(_make_resource(name, act, access_token, base_url))
    return out


class FacebookAdsConnector:
    """Meta Marketing API — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        account_id = str(params.get("account_id") or "").strip()
        access_token = secrets.get("access_token") or ""
        resources = parse_resources(str(params.get("resources") or "all"))
        api_version = str(params.get("api_version") or "v21.0").strip() or "v21.0"
        if not account_id:
            raise ValueError("Meta Ad Account ID majburiy")
        if not access_token:
            raise ValueError("Meta access_token majburiy")
        return facebook_ads_source(
            account_id=account_id,
            access_token=access_token,
            resources=resources,
            api_version=api_version,
        )
