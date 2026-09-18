from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict


class ResponseType(str, Enum):
    NORMAL = "NORMAL"
    DIRECT_ANSWER = "DIRECT_ANSWER"
    TOOL_RESULT = "TOOL_RESULT"
    SAFE_TEMPLATE = "SAFE_TEMPLATE"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"


@dataclass
class ConversationResult:
    """Final execution result for one prepared conversation turn.

    This is intentionally a result container only. It does not decide scene,
    dialogue state, memory, intent, or context transitions.
    """

    response: str
    response_type: ResponseType = ResponseType.NORMAL
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.response = str(self.response or "").strip()
        self.response_type = ResponseType(self.response_type)
        self.execution_status = ExecutionStatus(self.execution_status)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["response_type"] = self.response_type.value
        data["execution_status"] = self.execution_status.value
        return data
