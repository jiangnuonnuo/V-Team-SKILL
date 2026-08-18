"""V-Team 的 capability 双 Lane、契约、恢复与 Playbook 索引工具。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


STATE_VERSION = 3
LEGACY_STATE_VERSION = 2
STATE_RELATIVE_PATH = Path(".vteam/state.json")
SKILL_ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
URI_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://\S+$", re.IGNORECASE)
SECRET_PATTERN = re.compile(
    r"(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization|token)"
    r"\s*[:=]\s*\S+|-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----",
    re.IGNORECASE,
)
ROLE_PATTERN = re.compile(
    r"^(requirement|product|architect|backend|frontend|qa|operations)"
    r"(?:-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)?$"
)
ROLE_REFERENCES = {
    "requirement": "references/role-requirement.md",
    "product": "references/role-requirement.md",
    "architect": "references/role-architect.md",
    "backend": "references/role-backend.md",
    "frontend": "references/role-frontend.md",
    "qa": "references/role-qa.md",
    "operations": "references/role-operations.md",
}
CONTRACT_SOURCES = (
    "openapi",
    "graphql",
    "protobuf",
    "json-schema",
    "shared-types",
    "contract-test",
)
PUBLISHABLE_STATUSES = ("draft", "ready", "blocked")
DISCOVERABLE_STATUSES = frozenset({"draft", "ready", "verified", "blocked"})
INTEGRATION_STATUSES = frozenset({"ready", "verified"})
LANES = ("frontend", "backend")
LANE_INITIAL_STATUSES = ("required", "no-change", "blocked")
LANE_UPDATE_STATUSES = ("active", "blocked", "no-change")
LANE_FINISHED_STATUSES = frozenset({"completed", "no-change"})
PLAYBOOK_FUNCTIONS = ("development", "operations")
PLAYBOOK_STATUSES = ("draft", "verified")


class VTeamError(Exception):
    """可向用户说明的输入或状态错误。"""

    exit_code = 2


class SelectionRequired(VTeamError):
    """发现多个候选项，需要调用方明确选择。"""

    exit_code = 3


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def project_root_from(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise VTeamError(f"项目目录不存在: {root}")
    return root


def state_path(project_root: Path) -> Path:
    return project_root / STATE_RELATIVE_PATH


def empty_state(project_root: Path) -> dict[str, Any]:
    return {
        "schema_version": STATE_VERSION,
        "project": project_root.name,
        "capabilities": {},
        "contracts": {},
        "active": {},
        "playbooks": {},
        "milestones": [],
    }


def migrate_state(data: dict[str, Any]) -> dict[str, Any]:
    """兼容读取 v2；只有下次写入时才把文件落为 v3。"""
    version = data.get("schema_version")
    if version == STATE_VERSION:
        return data
    if version != LEGACY_STATE_VERSION:
        raise VTeamError(
            f"不支持的状态版本 {version!r}；支持 {LEGACY_STATE_VERSION} 和 {STATE_VERSION}"
        )
    migrated = dict(data)
    migrated["schema_version"] = STATE_VERSION
    migrated.setdefault("playbooks", {})
    return migrated


def load_state(project_root: Path) -> tuple[dict[str, Any], bool]:
    path = state_path(project_root)
    if not path.exists():
        return empty_state(project_root), False
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VTeamError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(raw_data, dict):
        raise VTeamError(f"状态文件根节点必须是 JSON object: {path}")
    data = migrate_state(raw_data)
    expected_types = {
        "capabilities": dict,
        "contracts": dict,
        "active": dict,
        "playbooks": dict,
        "milestones": list,
    }
    for field, expected_type in expected_types.items():
        if not isinstance(data.get(field), expected_type):
            raise VTeamError(f"状态字段 {field} 必须是 {expected_type.__name__}")
    return data, True


def save_state(project_root: Path, data: dict[str, Any]) -> Path:
    data["schema_version"] = STATE_VERSION
    path = state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        output.write(payload)
    temporary.replace(path)
    return path


def validate_id(value: str, label: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise VTeamError(
            f"{label} 必须以小写字母或数字开头，且只含小写字母、数字、点、"
            f"下划线或短横线: {value!r}"
        )
    return value


def validate_state_text(value: str, label: str, maximum: int = 512) -> str:
    """状态只容纳单行摘要/引用，拒绝凭据和完整日志。"""
    text = value.strip()
    if not text:
        raise VTeamError(f"{label}不能为空")
    if "\n" in text or "\r" in text:
        raise VTeamError(f"{label} 必须是单行摘要或引用，不能保存完整日志")
    if len(text) > maximum:
        raise VTeamError(f"{label} 长度不能超过 {maximum} 个字符")
    if SECRET_PATTERN.search(text):
        raise VTeamError(f"{label} 不能包含密钥或凭据")
    return text


def role_discipline(role_id: str) -> str:
    match = ROLE_PATTERN.fullmatch(role_id)
    if not match:
        raise VTeamError(
            "角色 ID 必须是 <职能>-<功能范围>，职能只能是 "
            "requirement/product/architect/backend/frontend/qa/operations: "
            f"{role_id!r}"
        )
    return match.group(1)


def unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def nonempty(values: Sequence[str] | None, label: str) -> list[str]:
    return unique(
        [validate_state_text(value, label) for value in (values or []) if value.strip()]
    )


def validate_source_ref(project_root: Path, value: str, label: str = "source_ref") -> str:
    source_ref = validate_state_text(value, label, maximum=1024)
    if URI_PATTERN.fullmatch(source_ref):
        return source_ref
    file_part = source_ref.split("#", 1)[0].split("::", 1)[0]
    if not file_part:
        raise VTeamError(f"本地 {label} 必须包含文件路径")
    relative_path = Path(file_part)
    if relative_path.is_absolute():
        raise VTeamError(f"本地 {label} 必须使用项目相对路径")
    resolved_path = (project_root / relative_path).resolve()
    try:
        resolved_path.relative_to(project_root)
    except ValueError as exc:
        raise VTeamError(f"本地 {label} 不得逃逸项目目录") from exc
    if not resolved_path.is_file():
        raise VTeamError(f"本地 {label} 文件不存在: {file_part}")
    return source_ref


def contract_for_output(contract: dict[str, Any]) -> dict[str, Any]:
    result = dict(contract)
    result["integration_allowed"] = contract.get("status") in INTEGRATION_STATUSES
    return result


def playbook_for_output(playbook: dict[str, Any]) -> dict[str, Any]:
    result = dict(playbook)
    result["usable"] = playbook.get("status") == "verified"
    return result


def emit(payload: Any, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def relevant_contracts(
    data: dict[str, Any], role_id: str, capability: str | None
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for contract in data["contracts"].values():
        if capability and contract.get("capability") != capability:
            continue
        if contract.get("status") not in DISCOVERABLE_STATUSES:
            continue
        if role_id != contract.get("provider") and role_id not in contract.get(
            "consumers", []
        ):
            continue
        matches.append(contract_for_output(contract))
    return sorted(matches, key=lambda item: item["id"])


def capability_lanes(capability_state: Any) -> dict[str, Any] | None:
    if not isinstance(capability_state, dict):
        return None
    lanes = capability_state.get("lanes")
    return lanes if isinstance(lanes, dict) else None


def command_context(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    discipline = role_discipline(args.role_id)
    capability = validate_id(args.capability, "capability") if args.capability else None
    if args.lane and discipline != args.lane:
        raise VTeamError("--lane 必须与当前角色职能一致")
    data, exists = load_state(root)
    capability_state = data["capabilities"].get(capability) if capability else None
    lanes = capability_lanes(capability_state)
    scoped_capability_state = capability_state
    if args.lane and isinstance(capability_state, dict) and lanes:
        scoped_capability_state = dict(capability_state)
        scoped_capability_state["lanes"] = {args.lane: lanes[args.lane]}
    emit(
        {
            "role_id": args.role_id,
            "discipline": discipline,
            "role_reference": str(SKILL_ROOT / ROLE_REFERENCES[discipline]),
            "capability": capability,
            "capability_state": scoped_capability_state,
            "lane": lanes.get(args.lane) if lanes and args.lane else None,
            "contracts": relevant_contracts(data, args.role_id, capability),
            "active": data["active"].get(capability) if capability else None,
            "milestone_count": len(data["milestones"]),
            "state_exists": exists,
        },
        args.json,
    )


def command_contract_publish(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    contract_id = validate_id(args.id, "contract id")
    capability = validate_id(args.capability, "capability")
    role_discipline(args.provider)
    consumers = unique(args.consumer)
    provider_evidence = nonempty(args.verification, "provider verification")
    for consumer in consumers:
        role_discipline(consumer)
    note = validate_state_text(args.note, "contract note") if args.note else None
    mock = validate_state_text(args.mock, "mock reference") if args.mock else None
    version = validate_state_text(args.version, "contract version")
    if args.status == "blocked" and not note:
        raise VTeamError("blocked 契约必须用 --note 说明阻塞原因")
    if args.status == "ready" and not provider_evidence:
        raise VTeamError("ready 契约必须用 --verification 提供一次直接验证证据")
    data, _ = load_state(root)
    existing = data["contracts"].get(contract_id)
    if existing:
        if existing.get("capability") != capability:
            raise VTeamError("同一 contract id 不得改变 capability")
        if existing.get("provider") != args.provider:
            raise VTeamError("同一 contract id 不得改变 provider")
    source_ref = validate_source_ref(root, args.source_ref)
    timestamp = utc_now()
    verification = list(existing.get("verification", [])) if existing else []
    verification.extend(
        {"by": args.provider, "evidence": item, "at": timestamp}
        for item in provider_evidence
    )
    contract: dict[str, Any] = {
        "id": contract_id,
        "capability": capability,
        "provider": args.provider,
        "consumers": consumers,
        "source": args.source,
        "source_ref": source_ref,
        "status": args.status,
        "version": version,
        "breaking": args.breaking,
        "verification": verification,
        "updated_at": timestamp,
        "created_at": existing.get("created_at", timestamp) if existing else timestamp,
    }
    if mock:
        contract["mock"] = mock
    elif existing and existing.get("mock"):
        contract["mock"] = existing["mock"]
    if note:
        contract["note"] = note
    elif args.status == "blocked" and existing and existing.get("note"):
        contract["note"] = existing["note"]
    data["contracts"][contract_id] = contract
    path = save_state(root, data)
    emit({"action": "published", "state": str(path), "contract": contract}, args.json)


def find_contract(data: dict[str, Any], contract_id: str) -> dict[str, Any]:
    contract = data["contracts"].get(contract_id)
    if not contract:
        raise VTeamError(f"契约不存在: {contract_id}")
    return contract


def command_contract_discover(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    role_discipline(args.consumer)
    data, _ = load_state(root)
    matches = sorted(
        [
            contract
            for contract in data["contracts"].values()
            if contract.get("capability") == capability
            and args.consumer in contract.get("consumers", [])
            and contract.get("status") in DISCOVERABLE_STATUSES
        ],
        key=lambda item: item["id"],
    )
    if args.contract_id:
        contract_id = validate_id(args.contract_id, "contract id")
        matches = [item for item in matches if item["id"] == contract_id]
        if not matches:
            raise VTeamError(
                f"未发现 capability={capability}、consumer={args.consumer}、"
                f"id={contract_id} 的可用契约"
            )
    if not matches:
        raise VTeamError(
            f"未发现 capability={capability}、consumer={args.consumer} 的契约；"
            "禁止猜测接口"
        )
    if len(matches) > 1:
        raise SelectionRequired(
            "发现多个契约，需要用 --contract-id 明确选择: "
            + ", ".join(item["id"] for item in matches)
        )
    emit(
        {"selection": "single", "contract": contract_for_output(matches[0])},
        args.json,
    )


def command_contract_verify(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    contract_id = validate_id(args.id, "contract id")
    role_discipline(args.verifier)
    evidence = validate_state_text(args.evidence, "消费者验证证据")
    data, _ = load_state(root)
    contract = find_contract(data, contract_id)
    if args.verifier not in contract.get("consumers", []):
        raise VTeamError(f"角色不是契约登记的 consumer: {args.verifier}")
    if contract.get("status") not in INTEGRATION_STATUSES:
        raise VTeamError(
            "只有 ready 或 verified 契约可以验证；请先由提供者发布可集成版本"
        )
    timestamp = utc_now()
    contract.setdefault("verification", []).append(
        {"by": args.verifier, "evidence": evidence, "at": timestamp}
    )
    contract["status"] = "verified"
    contract["updated_at"] = timestamp
    path = save_state(root, data)
    emit({"action": "verified", "state": str(path), "contract": contract}, args.json)


def command_contract_deprecate(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    contract_id = validate_id(args.id, "contract id")
    reason = validate_state_text(args.reason, "deprecation reason")
    if args.replacement:
        validate_id(args.replacement, "replacement contract id")
        if args.replacement == contract_id:
            raise VTeamError("替代契约不能是自身")
    data, _ = load_state(root)
    contract = find_contract(data, contract_id)
    timestamp = utc_now()
    contract["status"] = "deprecated"
    contract["deprecation"] = {
        "reason": reason,
        "replacement": args.replacement,
        "at": timestamp,
    }
    contract["updated_at"] = timestamp
    path = save_state(root, data)
    emit({"action": "deprecated", "state": str(path), "contract": contract}, args.json)


def lane_record(status: str, reason: str | None, timestamp: str) -> dict[str, Any]:
    record: dict[str, Any] = {"status": status, "updated_at": timestamp}
    if reason:
        record["reason"] = reason
    return record


def lane_reason(status: str, value: str | None, label: str) -> str | None:
    if status in {"no-change", "blocked"}:
        if not value:
            raise VTeamError(f"{label} 为 {status} 时必须提供 --reason")
        return validate_state_text(value, f"{label} reason")
    return validate_state_text(value, f"{label} reason") if value else None


def find_capability(data: dict[str, Any], capability: str) -> dict[str, Any]:
    entry = data["capabilities"].get(capability)
    if not isinstance(entry, dict):
        raise VTeamError(f"capability 不存在: {capability}")
    return entry


def require_lanes(entry: dict[str, Any]) -> dict[str, Any]:
    lanes = capability_lanes(entry)
    if not lanes or any(lane not in lanes for lane in LANES):
        raise VTeamError("capability 尚未定义完整 frontend/backend Lane")
    return lanes


def command_capability_define(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.id, "capability")
    summary = validate_state_text(args.summary, "capability summary")
    frontend_reason = lane_reason(args.frontend, args.frontend_reason, "frontend Lane")
    backend_reason = lane_reason(args.backend, args.backend_reason, "backend Lane")
    data, _ = load_state(root)
    if capability in data["capabilities"]:
        raise VTeamError(f"capability 已存在，使用 lane 命令更新: {capability}")
    timestamp = utc_now()
    definition = {
        "status": "planned",
        "summary": summary,
        "lanes": {
            "frontend": lane_record(args.frontend, frontend_reason, timestamp),
            "backend": lane_record(args.backend, backend_reason, timestamp),
        },
        "contracts": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    data["capabilities"][capability] = definition
    path = save_state(root, data)
    emit(
        {
            "action": "capability-defined",
            "state": str(path),
            "capability": capability,
            "definition": definition,
        },
        args.json,
    )


def command_lane_update(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    reason = lane_reason(args.status, args.reason, f"{args.lane} Lane")
    summary = validate_state_text(args.summary, "lane summary") if args.summary else None
    references = nonempty(args.reference, "lane reference")
    data, _ = load_state(root)
    entry = find_capability(data, capability)
    lanes = require_lanes(entry)
    if lanes[args.lane].get("status") == "completed":
        raise VTeamError(f"{args.lane} Lane 已完成，不能再次更新")
    timestamp = utc_now()
    record = lane_record(args.status, reason, timestamp)
    if summary:
        record["summary"] = summary
    if references:
        record["references"] = references
    lanes[args.lane] = record
    entry["status"] = "active"
    entry["updated_at"] = timestamp
    path = save_state(root, data)
    emit(
        {
            "action": "lane-no-change" if args.status == "no-change" else "lane-updated",
            "state": str(path),
            "capability": capability,
            "lane": args.lane,
            "state_record": record,
        },
        args.json,
    )


def command_lane_no_change(args: argparse.Namespace) -> None:
    args.status = "no-change"
    command_lane_update(args)


def command_lane_complete(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    summary = validate_state_text(args.summary, "lane summary")
    evidence = nonempty(args.verification, "lane verification")
    if not evidence:
        raise VTeamError("Lane 完成必须提供一条非空验证证据")
    data, _ = load_state(root)
    entry = find_capability(data, capability)
    lanes = require_lanes(entry)
    current_status = lanes[args.lane].get("status")
    if current_status == "no-change":
        raise VTeamError(f"{args.lane} Lane 标记为 no-change，不能再完成")
    if current_status == "blocked":
        raise VTeamError(f"{args.lane} Lane 仍为 blocked，请先更新为 active")
    timestamp = utc_now()
    record = {
        "status": "completed",
        "summary": summary,
        "verification": evidence,
        "completed_at": timestamp,
        "updated_at": timestamp,
    }
    lanes[args.lane] = record
    entry["status"] = "active"
    entry["updated_at"] = timestamp
    path = save_state(root, data)
    emit(
        {
            "action": "lane-completed",
            "state": str(path),
            "capability": capability,
            "lane": args.lane,
            "state_record": record,
        },
        args.json,
    )


def validate_completion_contracts(
    data: dict[str, Any], capability: str, contract_ids: Sequence[str]
) -> list[str]:
    result = unique(contract_ids)
    for contract_id in result:
        validate_id(contract_id, "contract id")
        contract = find_contract(data, contract_id)
        if contract.get("capability") != capability:
            raise VTeamError(f"契约 {contract_id} 不属于 capability {capability}")
        if contract.get("status") not in INTEGRATION_STATUSES:
            raise VTeamError(
                f"契约 {contract_id} 状态为 {contract.get('status')}，"
                "模块完成前必须是 ready 或 verified"
            )
    return result


def complete_capability(
    args: argparse.Namespace, require_defined_lanes: bool, action: str
) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    summary = validate_state_text(args.summary, "capability completion summary")
    evidence = nonempty(args.verification, "capability verification")
    if not evidence:
        raise VTeamError("模块完成必须提供一条非空验证证据")
    data, _ = load_state(root)
    existing = data["capabilities"].get(capability)
    if require_defined_lanes:
        if not isinstance(existing, dict):
            raise VTeamError("capability complete 前必须先 capability define")
        lanes = require_lanes(existing)
        unfinished = [
            lane for lane in LANES if lanes[lane].get("status") not in LANE_FINISHED_STATUSES
        ]
        if unfinished:
            raise VTeamError(
                "capability 完成前 frontend/backend Lane 必须均为 completed 或 no-change: "
                + ", ".join(unfinished)
            )
    contracts = validate_completion_contracts(data, capability, args.contract or [])
    timestamp = utc_now()
    completed = dict(existing) if isinstance(existing, dict) else {}
    completed.update(
        {
            "status": "completed",
            "summary": summary,
            "contracts": contracts,
            "verification": evidence,
            "completed_at": timestamp,
            "updated_at": timestamp,
        }
    )
    data["capabilities"][capability] = completed
    cleared_active = data["active"].pop(capability, None) is not None
    path = save_state(root, data)
    emit(
        {
            "action": action,
            "state": str(path),
            "capability": capability,
            "completed": completed,
            "cleared_active": cleared_active,
        },
        args.json,
    )


def command_capability_complete(args: argparse.Namespace) -> None:
    complete_capability(args, True, "capability-complete")


def command_module_complete(args: argparse.Namespace) -> None:
    """兼容 v2 模块完成调用；新能力应使用 capability complete。"""
    complete_capability(args, False, "module-complete")


def command_resume_set(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    role_discipline(args.role)
    summary = validate_state_text(args.summary, "resume summary")
    next_step = validate_state_text(args.next_step, "resume next_step")
    blocker = validate_state_text(args.blocker, "resume blocker") if args.blocker else None
    references = nonempty(args.reference, "resume reference")
    data, _ = load_state(root)
    record: dict[str, Any] = {
        "capability": capability,
        "role": args.role,
        "summary": summary,
        "next_step": next_step,
        "updated_at": utc_now(),
    }
    if args.function:
        record["function"] = args.function
    if blocker:
        record["blocker"] = blocker
    if references:
        record["references"] = references
    data["active"][capability] = record
    path = save_state(root, data)
    emit({"action": "resume-set", "state": str(path), "active": record}, args.json)


def command_resume_clear(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    data, exists = load_state(root)
    if not exists or capability not in data["active"]:
        emit({"action": "resume-clear", "cleared": False}, args.json)
        return
    del data["active"][capability]
    path = save_state(root, data)
    emit({"action": "resume-clear", "cleared": True, "state": str(path)}, args.json)


def playbook_role_is_valid(function: str, role: str) -> None:
    discipline = role_discipline(role)
    valid = (
        function == "development" and discipline in {"frontend", "backend"}
    ) or (function == "operations" and discipline == "operations")
    if not valid:
        raise VTeamError(f"function={function} 不允许 role={role}")


def find_playbook(data: dict[str, Any], playbook_id: str) -> dict[str, Any]:
    playbook = data["playbooks"].get(playbook_id)
    if not playbook:
        raise VTeamError(f"Playbook 不存在: {playbook_id}")
    return playbook


def command_playbook_publish(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    playbook_id = validate_id(args.id, "playbook id")
    action = validate_id(args.action, "playbook action")
    playbook_role_is_valid(args.function, args.role)
    source_ref = validate_source_ref(root, args.source_ref, "playbook source_ref")
    preconditions = nonempty(args.precondition, "playbook precondition")
    success_checks = nonempty(args.success_check, "playbook success_check")
    evidence = nonempty(args.verification, "playbook verification")
    rollback_ref = (
        validate_source_ref(root, args.rollback_ref, "playbook rollback_ref")
        if args.rollback_ref
        else None
    )
    if not success_checks:
        raise VTeamError("Playbook 必须提供至少一条 --success-check")
    if args.function == "operations" and not rollback_ref:
        raise VTeamError("operations Playbook 必须提供 --rollback-ref")
    if args.status == "verified" and not evidence:
        raise VTeamError("verified Playbook 必须提供一次直接验证证据")
    data, _ = load_state(root)
    existing = data["playbooks"].get(playbook_id)
    if existing:
        for field, value in (
            ("function", args.function),
            ("role", args.role),
            ("action", action),
        ):
            if existing.get(field) != value:
                raise VTeamError(f"同一 playbook id 不得改变 {field}")
    timestamp = utc_now()
    verification = list(existing.get("verification", [])) if existing else []
    verification.extend(
        {"by": args.role, "evidence": item, "at": timestamp} for item in evidence
    )
    playbook: dict[str, Any] = {
        "id": playbook_id,
        "function": args.function,
        "role": args.role,
        "action": action,
        "source_ref": source_ref,
        "preconditions": preconditions,
        "success_checks": success_checks,
        "status": args.status,
        "verification": verification,
        "updated_at": timestamp,
        "created_at": existing.get("created_at", timestamp) if existing else timestamp,
    }
    if rollback_ref:
        playbook["rollback_ref"] = rollback_ref
    elif existing and existing.get("rollback_ref"):
        playbook["rollback_ref"] = existing["rollback_ref"]
    data["playbooks"][playbook_id] = playbook
    path = save_state(root, data)
    emit({"action": "playbook-published", "state": str(path), "playbook": playbook}, args.json)


def command_playbook_discover(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    action = validate_id(args.action, "playbook action")
    playbook_role_is_valid(args.function, args.role)
    data, _ = load_state(root)
    matches = sorted(
        [
            item
            for item in data["playbooks"].values()
            if item.get("function") == args.function
            and item.get("role") == args.role
            and item.get("action") == action
            and item.get("status") == "verified"
        ],
        key=lambda item: item["id"],
    )
    if args.playbook_id:
        playbook_id = validate_id(args.playbook_id, "playbook id")
        matches = [item for item in matches if item["id"] == playbook_id]
        if not matches:
            raise VTeamError(f"未发现 id={playbook_id} 的可用 Playbook")
    if not matches:
        raise VTeamError(
            f"未发现 function={args.function}、role={args.role}、action={action} 的已验证 Playbook"
        )
    if len(matches) > 1:
        raise SelectionRequired(
            "发现多个 Playbook，需要用 --playbook-id 明确选择: "
            + ", ".join(item["id"] for item in matches)
        )
    emit({"selection": "single", "playbook": playbook_for_output(matches[0])}, args.json)


def command_playbook_verify(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    playbook_id = validate_id(args.id, "playbook id")
    role_discipline(args.verifier)
    evidence = validate_state_text(args.evidence, "Playbook 验证证据")
    data, _ = load_state(root)
    playbook = find_playbook(data, playbook_id)
    if playbook.get("status") == "deprecated":
        raise VTeamError("已停用 Playbook 不能验证；请发布新的 Playbook")
    timestamp = utc_now()
    playbook.setdefault("verification", []).append(
        {"by": args.verifier, "evidence": evidence, "at": timestamp}
    )
    playbook["status"] = "verified"
    playbook["updated_at"] = timestamp
    path = save_state(root, data)
    emit({"action": "playbook-verified", "state": str(path), "playbook": playbook}, args.json)


def command_playbook_deprecate(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    playbook_id = validate_id(args.id, "playbook id")
    reason = validate_state_text(args.reason, "playbook deprecation reason")
    data, _ = load_state(root)
    playbook = find_playbook(data, playbook_id)
    timestamp = utc_now()
    playbook["status"] = "deprecated"
    playbook["deprecation"] = {"reason": reason, "at": timestamp}
    playbook["updated_at"] = timestamp
    path = save_state(root, data)
    emit({"action": "playbook-deprecated", "state": str(path), "playbook": playbook}, args.json)


def command_milestone_record(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    milestone_id = validate_id(args.id, "milestone id")
    capability = validate_id(args.capability, "capability")
    summary = validate_state_text(args.summary, "milestone summary")
    references = nonempty(args.reference, "milestone reference")
    data, _ = load_state(root)
    if any(item.get("id") == milestone_id for item in data["milestones"]):
        raise VTeamError(f"里程碑已存在: {milestone_id}")
    milestone = {
        "id": milestone_id,
        "capability": capability,
        "summary": summary,
        "references": references,
        "recorded_at": utc_now(),
    }
    data["milestones"].append(milestone)
    path = save_state(root, data)
    emit({"action": "milestone-recorded", "state": str(path), "milestone": milestone}, args.json)


def command_milestone_list(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    data, _ = load_state(root)
    items = data["milestones"]
    if args.capability:
        capability = validate_id(args.capability, "capability")
        items = [item for item in items if item.get("capability") == capability]
    emit(
        {
            "milestones": [
                {
                    "id": item["id"],
                    "capability": item["capability"],
                    "summary": item["summary"],
                }
                for item in items
            ]
        },
        args.json,
    )


def command_milestone_show(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    milestone_id = validate_id(args.id, "milestone id")
    data, _ = load_state(root)
    for item in data["milestones"]:
        if item.get("id") == milestone_id:
            emit({"milestone": item}, args.json)
            return
    raise VTeamError(f"里程碑不存在: {milestone_id}")


def add_project_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", required=True, help="产品项目根目录")


def add_json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="输出单行 JSON")


def add_completion_arguments(parser: argparse.ArgumentParser) -> None:
    add_project_argument(parser)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--verification", action="append", required=True)
    parser.add_argument("--contract", action="append")
    add_json_argument(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="V-Team capability 双 Lane、契约与 Playbook 索引（普通任务无需使用）"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    context_parser = commands.add_parser("context", help="读取当前角色的最小上下文")
    add_project_argument(context_parser)
    context_parser.add_argument("--role-id", required=True)
    context_parser.add_argument("--capability")
    context_parser.add_argument("--lane", choices=LANES)
    add_json_argument(context_parser)
    context_parser.set_defaults(handler=command_context)

    capability_parser = commands.add_parser("capability", help="定义并完成完整产品 capability")
    capability_commands = capability_parser.add_subparsers(dest="capability_command", required=True)
    define = capability_commands.add_parser("define", help="定义 frontend/backend 双 Lane")
    add_project_argument(define)
    define.add_argument("--id", required=True)
    define.add_argument("--summary", required=True)
    define.add_argument("--frontend", choices=LANE_INITIAL_STATUSES, required=True)
    define.add_argument("--frontend-reason")
    define.add_argument("--backend", choices=LANE_INITIAL_STATUSES, required=True)
    define.add_argument("--backend-reason")
    add_json_argument(define)
    define.set_defaults(handler=command_capability_define)
    capability_complete = capability_commands.add_parser(
        "complete", help="确认双 Lane 完成并清除恢复状态"
    )
    add_completion_arguments(capability_complete)
    capability_complete.set_defaults(handler=command_capability_complete)

    lane_parser = commands.add_parser("lane", help="维护 capability 的 frontend/backend 工作流")
    lane_commands = lane_parser.add_subparsers(dest="lane_command", required=True)
    lane_update = lane_commands.add_parser("update", help="更新 Lane 为 active、blocked 或 no-change")
    add_project_argument(lane_update)
    lane_update.add_argument("--capability", required=True)
    lane_update.add_argument("--lane", choices=LANES, required=True)
    lane_update.add_argument("--status", choices=LANE_UPDATE_STATUSES, required=True)
    lane_update.add_argument("--reason")
    lane_update.add_argument("--summary")
    lane_update.add_argument("--reference", action="append")
    add_json_argument(lane_update)
    lane_update.set_defaults(handler=command_lane_update)
    lane_no_change = lane_commands.add_parser(
        "no-change", help="明确记录无需修改的 Lane 及其依据"
    )
    add_project_argument(lane_no_change)
    lane_no_change.add_argument("--capability", required=True)
    lane_no_change.add_argument("--lane", choices=LANES, required=True)
    lane_no_change.add_argument("--reason", required=True)
    lane_no_change.add_argument("--summary")
    lane_no_change.add_argument("--reference", action="append")
    add_json_argument(lane_no_change)
    lane_no_change.set_defaults(handler=command_lane_no_change)
    lane_complete = lane_commands.add_parser("complete", help="记录 Lane 完成和直接验证证据")
    add_project_argument(lane_complete)
    lane_complete.add_argument("--capability", required=True)
    lane_complete.add_argument("--lane", choices=LANES, required=True)
    lane_complete.add_argument("--summary", required=True)
    lane_complete.add_argument("--verification", action="append", required=True)
    add_json_argument(lane_complete)
    lane_complete.set_defaults(handler=command_lane_complete)

    contract_parser = commands.add_parser("contract", help="管理跨角色契约索引")
    contract_commands = contract_parser.add_subparsers(dest="contract_command", required=True)
    publish = contract_commands.add_parser("publish", help="创建或更新契约索引")
    add_project_argument(publish)
    publish.add_argument("--id", required=True)
    publish.add_argument("--capability", required=True)
    publish.add_argument("--provider", required=True)
    publish.add_argument("--consumer", action="append", required=True)
    publish.add_argument("--source", choices=CONTRACT_SOURCES, required=True)
    publish.add_argument("--source-ref", required=True)
    publish.add_argument("--status", choices=PUBLISHABLE_STATUSES, default="draft")
    publish.add_argument("--version", default="1")
    publish.add_argument("--breaking", action="store_true")
    publish.add_argument("--mock")
    publish.add_argument("--note")
    publish.add_argument("--verification", action="append")
    add_json_argument(publish)
    publish.set_defaults(handler=command_contract_publish)
    discover = contract_commands.add_parser("discover", help="按能力和消费者发现契约")
    add_project_argument(discover)
    discover.add_argument("--capability", required=True)
    discover.add_argument("--consumer", required=True)
    discover.add_argument("--contract-id")
    add_json_argument(discover)
    discover.set_defaults(handler=command_contract_discover)
    verify = contract_commands.add_parser("verify", help="记录消费者验证")
    add_project_argument(verify)
    verify.add_argument("--id", required=True)
    verify.add_argument("--verifier", required=True)
    verify.add_argument("--evidence", required=True)
    add_json_argument(verify)
    verify.set_defaults(handler=command_contract_verify)
    deprecate = contract_commands.add_parser("deprecate", help="停用契约")
    add_project_argument(deprecate)
    deprecate.add_argument("--id", required=True)
    deprecate.add_argument("--reason", required=True)
    deprecate.add_argument("--replacement")
    add_json_argument(deprecate)
    deprecate.set_defaults(handler=command_contract_deprecate)

    resume_parser = commands.add_parser("resume", help="维护跨会话的单条恢复状态")
    resume_commands = resume_parser.add_subparsers(dest="resume_command", required=True)
    resume_set = resume_commands.add_parser("set", help="覆盖当前 capability 的恢复状态")
    add_project_argument(resume_set)
    resume_set.add_argument("--capability", required=True)
    resume_set.add_argument("--role", required=True)
    resume_set.add_argument(
        "--function",
        choices=("discovery", "requirement", "solution", "development", "review", "operations"),
    )
    resume_set.add_argument("--summary", required=True)
    resume_set.add_argument("--next-step", required=True)
    resume_set.add_argument("--blocker")
    resume_set.add_argument("--reference", action="append")
    add_json_argument(resume_set)
    resume_set.set_defaults(handler=command_resume_set)
    resume_clear = resume_commands.add_parser("clear", help="清除指定 capability 的恢复状态")
    add_project_argument(resume_clear)
    resume_clear.add_argument("--capability", required=True)
    add_json_argument(resume_clear)
    resume_clear.set_defaults(handler=command_resume_clear)

    module_parser = commands.add_parser("module", help="兼容旧调用的模块完成记录")
    module_commands = module_parser.add_subparsers(dest="module_command", required=True)
    module_complete = module_commands.add_parser("complete", help="完成模块并清除恢复状态")
    add_completion_arguments(module_complete)
    module_complete.set_defaults(handler=command_module_complete)

    playbook_parser = commands.add_parser("playbook", help="管理经验证的开发与运维操作索引")
    playbook_commands = playbook_parser.add_subparsers(dest="playbook_command", required=True)
    playbook_publish = playbook_commands.add_parser("publish", help="创建或更新 Playbook 索引")
    add_project_argument(playbook_publish)
    playbook_publish.add_argument("--id", required=True)
    playbook_publish.add_argument("--function", choices=PLAYBOOK_FUNCTIONS, required=True)
    playbook_publish.add_argument("--role", required=True)
    playbook_publish.add_argument("--action", required=True)
    playbook_publish.add_argument("--source-ref", required=True)
    playbook_publish.add_argument("--precondition", action="append")
    playbook_publish.add_argument("--success-check", action="append", required=True)
    playbook_publish.add_argument("--rollback-ref")
    playbook_publish.add_argument("--status", choices=PLAYBOOK_STATUSES, default="draft")
    playbook_publish.add_argument("--verification", action="append")
    add_json_argument(playbook_publish)
    playbook_publish.set_defaults(handler=command_playbook_publish)
    playbook_discover = playbook_commands.add_parser("discover", help="发现一个已验证 Playbook")
    add_project_argument(playbook_discover)
    playbook_discover.add_argument("--function", choices=PLAYBOOK_FUNCTIONS, required=True)
    playbook_discover.add_argument("--role", required=True)
    playbook_discover.add_argument("--action", required=True)
    playbook_discover.add_argument("--playbook-id")
    add_json_argument(playbook_discover)
    playbook_discover.set_defaults(handler=command_playbook_discover)
    playbook_verify = playbook_commands.add_parser("verify", help="记录 Playbook 的直接验证")
    add_project_argument(playbook_verify)
    playbook_verify.add_argument("--id", required=True)
    playbook_verify.add_argument("--verifier", required=True)
    playbook_verify.add_argument("--evidence", required=True)
    add_json_argument(playbook_verify)
    playbook_verify.set_defaults(handler=command_playbook_verify)
    playbook_deprecate = playbook_commands.add_parser("deprecate", help="停用 Playbook")
    add_project_argument(playbook_deprecate)
    playbook_deprecate.add_argument("--id", required=True)
    playbook_deprecate.add_argument("--reason", required=True)
    add_json_argument(playbook_deprecate)
    playbook_deprecate.set_defaults(handler=command_playbook_deprecate)

    milestone_parser = commands.add_parser("milestone", help="显式维护重大里程碑引用")
    milestone_commands = milestone_parser.add_subparsers(dest="milestone_command", required=True)
    record = milestone_commands.add_parser("record", help="记录重大里程碑")
    add_project_argument(record)
    record.add_argument("--id", required=True)
    record.add_argument("--capability", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--reference", action="append", required=True)
    add_json_argument(record)
    record.set_defaults(handler=command_milestone_record)
    milestone_list = milestone_commands.add_parser("list", help="列出紧凑里程碑索引")
    add_project_argument(milestone_list)
    milestone_list.add_argument("--capability")
    add_json_argument(milestone_list)
    milestone_list.set_defaults(handler=command_milestone_list)
    milestone_show = milestone_commands.add_parser("show", help="读取一个里程碑")
    add_project_argument(milestone_show)
    milestone_show.add_argument("--id", required=True)
    add_json_argument(milestone_show)
    milestone_show.set_defaults(handler=command_milestone_show)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except VTeamError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return exc.exit_code
    except OSError as exc:
        print(f"文件操作失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
