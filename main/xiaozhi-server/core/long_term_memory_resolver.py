from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.manage_api_client import ManageApiClient

from core.interest_key_normalizer import normalize_interest_keys
from core.profile_resolver import normalize_age_group, map_age_to_group


DEFAULT_AGE_GROUP = "6-8"


@dataclass(frozen=True)
class RuntimeLongTermMemory:
    nickname_preference: str = ""
    age: Optional[int] = None
    age_group: str = DEFAULT_AGE_GROUP
    robot_name_preference: str = ""
    interests: List[str] = field(default_factory=list)
    favorite_dog_types: List[str] = field(default_factory=list)
    desired_activities: List[str] = field(default_factory=list)
    parent_goals: List[str] = field(default_factory=list)
    extra_attributes: Dict[str, Any] = field(default_factory=dict)
    profile_version: int = 1


def _normalize_string(value: Any) -> str:
    return str(value or "").strip()


def _normalize_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_normalize_string(v) for v in value) if item]


def _normalize_object_map(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _normalize_string(raw_key)
        if key:
            normalized[key] = raw_value
    return normalized


def build_runtime_long_term_memory(payload: Optional[Dict[str, Any]]) -> RuntimeLongTermMemory:
    if not isinstance(payload, dict):
        return RuntimeLongTermMemory()

    long_term_memory = payload.get("longTermMemory")
    if not isinstance(long_term_memory, dict):
        long_term_memory = payload

    age = _normalize_int(long_term_memory.get("age"))
    age_group = normalize_age_group(long_term_memory.get("ageGroup") or long_term_memory.get("age_group"))
    if age_group == DEFAULT_AGE_GROUP:
        age_group = map_age_to_group(age)

    profile_version = _normalize_int(long_term_memory.get("profileVersion")) or 1

    return RuntimeLongTermMemory(
        nickname_preference=_normalize_string(long_term_memory.get("nicknamePreference")),
        age=age,
        age_group=age_group,
        robot_name_preference=_normalize_string(long_term_memory.get("robotNamePreference")),
        interests=normalize_interest_keys(_normalize_string_list(long_term_memory.get("interests"))),
        favorite_dog_types=_normalize_string_list(long_term_memory.get("favoriteDogTypes")),
        desired_activities=_normalize_string_list(long_term_memory.get("desiredActivities")),
        parent_goals=_normalize_string_list(long_term_memory.get("parentGoals")),
        extra_attributes=_normalize_object_map(long_term_memory.get("extraAttributes")),
        profile_version=profile_version,
    )


async def resolve_long_term_memory_for_device(device_id: str | None) -> RuntimeLongTermMemory:
    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id or not ManageApiClient._instance:
        return RuntimeLongTermMemory()

    try:
        payload = await ManageApiClient._instance._execute_async_request(
            "GET",
            "/api/v1/child-profile/long-term-memory/active",
            params={"device_id": normalized_device_id},
        )
        return build_runtime_long_term_memory(payload)
    except Exception:
        return RuntimeLongTermMemory()
