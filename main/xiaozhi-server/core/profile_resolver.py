from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.manage_api_client import ManageApiClient


DEFAULT_AGE_GROUP = "6-8"


@dataclass(frozen=True)
class RuntimeChildProfile:
    nickname: str = ""
    age: Optional[int] = None
    age_group: str = DEFAULT_AGE_GROUP

    @property
    def age_band(self) -> str:
        return self.age_group or DEFAULT_AGE_GROUP


def normalize_age_group(age_group: str | None) -> str:
    normalized = str(age_group or "").strip()
    if normalized in {"3-5", "6-8", "9-11"}:
        return normalized
    if normalized == "9-12":
        return "9-11"
    return DEFAULT_AGE_GROUP


def map_age_to_group(age: Any) -> str:
    try:
        numeric_age = int(age)
    except (TypeError, ValueError):
        return DEFAULT_AGE_GROUP

    if 3 <= numeric_age <= 5:
        return "3-5"
    if 6 <= numeric_age <= 8:
        return "6-8"
    if 9 <= numeric_age <= 11:
        return "9-11"
    return DEFAULT_AGE_GROUP


def build_runtime_child_profile(payload: Optional[Dict[str, Any]]) -> RuntimeChildProfile:
    if not isinstance(payload, dict):
        return RuntimeChildProfile()

    child_profile = payload.get("childProfile")
    if not isinstance(child_profile, dict):
        child_profile = payload

    nickname = str(child_profile.get("nickname") or "").strip()
    age = child_profile.get("age")
    age_group = normalize_age_group(child_profile.get("ageGroup") or child_profile.get("age_group"))
    if age_group == DEFAULT_AGE_GROUP:
        age_group = map_age_to_group(age)

    try:
        normalized_age = int(age) if age is not None else None
    except (TypeError, ValueError):
        normalized_age = None

    return RuntimeChildProfile(nickname=nickname, age=normalized_age, age_group=age_group)


async def resolve_child_profile_for_device(device_id: str | None) -> RuntimeChildProfile:
    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id or not ManageApiClient._instance:
        return RuntimeChildProfile()

    try:
        payload = await ManageApiClient._instance._execute_async_request(
            "GET",
            "/api/v1/child-profile/active",
            params={"device_id": normalized_device_id},
        )
        return build_runtime_child_profile(payload)
    except Exception:
        return RuntimeChildProfile()
