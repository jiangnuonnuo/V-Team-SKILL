"""V-Team 的轻量 capability 状态与契约索引工具。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


STATE_VERSION = 2
STATE_RELATIVE_PATH = Path(".vteam/state.json")
SKILL_ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
URI_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://\S+$", re.IGNORECASE)
ROLE_PATTERN = re.compile(
    r"^(requirement|product|architect|backend|frontend|qa)"
    r"(?:-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)?$"
)
ROLE_REFERENCES = {
    "requirement": "references/role-requirement.md",
    "product": "references/role-requirement.md",
    "architect": "references/role-architect.md",
    "backend": "references/role-backend.md",
    "frontend": "references/role-frontend.md",
    "qa": "references/role-qa.md",
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


class VTeamError(Exception):
    """可向用户说明的输入或状态错误。"""

    exit_code = 2


class SelectionRequired(VTeamError):
    """发现多个契约，需要调用方明确选择。"""

    exit_code = 3


def utc_now() -> str:
    """返回秒级 UTC 时间，便于人和工具共同读取。"""
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
        "milestones": [],
    }


def load_state(project_root: Path) -> tuple[dict[str, Any], bool]:
    path = state_path(project_root)
    if not path.exists():
        return empty_state(project_root), False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VTeamError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise VTeamError(f"状态文件根节点必须是 JSON object: {path}")
    if data.get("schema_version") != STATE_VERSION:
        raise VTeamError(
            f"不支持的状态版本 {data.get('schema_version')!r}；"
            f"当前需要 {STATE_VERSION}"
        )
    expected_types = {
        "capabilities": dict,
        "contracts": dict,
        "active": dict,
        "milestones": list,
    }
    for field, expected_type in expected_types.items():
        if not isinstance(data.get(field), expected_type):
            raise VTeamError(f"状态字段 {field} 必须是 {expected_type.__name__}")
    return data, True


def save_state(project_root: Path, data: dict[str, Any]) -> Path:
    """原子覆盖唯一状态文件，不产生历史副本。"""
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


def role_discipline(role_id: str) -> str:
    match = ROLE_PATTERN.fullmatch(role_id)
    if not match:
        raise VTeamError(
            "角色 ID 必须是 <职能>-<功能范围>，职能只能是 "
            "requirement/product/architect/backend/frontend/qa: "
            f"{role_id!r}"
        )
    return match.group(1)


def unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def nonempty(values: Sequence[str] | None) -> list[str]:
    return [value.strip() for value in (values or []) if value.strip()]


def validate_source_ref(project_root: Path, value: str) -> str:
    """校验契约来源：外部 URI 明确可定位，本地引用必须指向项目内文件。"""
    source_ref = value.strip()
    if not source_ref:
        raise VTeamError("source_ref 不能为空")
    if URI_PATTERN.fullmatch(source_ref):
        return source_ref

    file_part = source_ref.split("#", 1)[0].split("::", 1)[0]
    if not file_part:
        raise VTeamError("本地 source_ref 必须包含文件路径")
    relative_path = Path(file_part)
    if relative_path.is_absolute():
        raise VTeamError("本地 source_ref 必须使用项目相对路径")
    resolved_path = (project_root / relative_path).resolve()
    try:
        resolved_path.relative_to(project_root)
    except ValueError as exc:
        raise VTeamError("本地 source_ref 不得逃逸项目目录") from exc
    if not resolved_path.is_file():
        raise VTeamError(f"本地 source_ref 文件不存在: {file_part}")
    return source_ref


def contract_for_output(contract: dict[str, Any]) -> dict[str, Any]:
    result = dict(contract)
    result["integration_allowed"] = contract.get("status") in INTEGRATION_STATUSES
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


def command_context(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    discipline = role_discipline(args.role_id)
    capability = (
        validate_id(args.capability, "capability") if args.capability else None
    )
    data, exists = load_state(root)
    payload = {
        "role_id": args.role_id,
        "discipline": discipline,
        "role_reference": str(SKILL_ROOT / ROLE_REFERENCES[discipline]),
        "capability": capability,
        "capability_state": data["capabilities"].get(capability) if capability else None,
        "contracts": relevant_contracts(data, args.role_id, capability),
        "active": data["active"].get(capability) if capability else None,
        "milestone_count": len(data["milestones"]),
        "state_exists": exists,
    }
    emit(payload, args.json)


def verification_entries(
    actor: str, evidence: Sequence[str] | None, timestamp: str
) -> list[dict[str, str]]:
    return [
        {"by": actor, "evidence": item, "at": timestamp}
        for item in (evidence or [])
    ]


def command_contract_publish(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    contract_id = validate_id(args.id, "contract id")
    capability = validate_id(args.capability, "capability")
    role_discipline(args.provider)
    consumers = unique(args.consumer)
    provider_evidence = nonempty(args.verification)
    for consumer in consumers:
        role_discipline(consumer)
    if args.status == "blocked" and not args.note:
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
    verification.extend(verification_entries(args.provider, provider_evidence, timestamp))
    contract: dict[str, Any] = {
        "id": contract_id,
        "capability": capability,
        "provider": args.provider,
        "consumers": consumers,
        "source": args.source,
        "source_ref": source_ref,
        "status": args.status,
        "version": args.version,
        "breaking": args.breaking,
        "verification": verification,
        "updated_at": timestamp,
    }
    if existing and "created_at" in existing:
        contract["created_at"] = existing["created_at"]
    else:
        contract["created_at"] = timestamp
    if args.mock:
        contract["mock"] = args.mock
    elif existing and existing.get("mock"):
        contract["mock"] = existing["mock"]
    if args.note:
        contract["note"] = args.note
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


def discover_contracts(
    data: dict[str, Any], capability: str, consumer: str
) -> list[dict[str, Any]]:
    return sorted(
        [
            contract
            for contract in data["contracts"].values()
            if contract.get("capability") == capability
            and consumer in contract.get("consumers", [])
            and contract.get("status") in DISCOVERABLE_STATUSES
        ],
        key=lambda item: item["id"],
    )


def command_contract_discover(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    role_discipline(args.consumer)
    data, _ = load_state(root)
    matches = discover_contracts(data, capability, args.consumer)

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
        candidates = ", ".join(item["id"] for item in matches)
        raise SelectionRequired(
            f"发现多个契约，需要用 --contract-id 明确选择: {candidates}"
        )

    emit(
        {
            "selection": "single",
            "contract": contract_for_output(matches[0]),
        },
        args.json,
    )


def command_contract_verify(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    contract_id = validate_id(args.id, "contract id")
    role_discipline(args.verifier)
    data, _ = load_state(root)
    contract = find_contract(data, contract_id)
    if args.verifier not in contract.get("consumers", []):
        raise VTeamError(f"角色不是契约登记的 consumer: {args.verifier}")
    if contract.get("status") not in INTEGRATION_STATUSES:
        raise VTeamError(
            "只有 ready 或 verified 契约可以验证；请先由提供者发布可集成版本"
        )
    evidence = args.evidence.strip()
    if not evidence:
        raise VTeamError("消费者验证证据不能为空")
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
    if args.replacement:
        validate_id(args.replacement, "replacement contract id")
        if args.replacement == contract_id:
            raise VTeamError("替代契约不能是自身")
    data, _ = load_state(root)
    contract = find_contract(data, contract_id)
    contract["status"] = "deprecated"
    contract["deprecation"] = {
        "reason": args.reason,
        "replacement": args.replacement,
        "at": utc_now(),
    }
    contract["updated_at"] = contract["deprecation"]["at"]
    path = save_state(root, data)
    emit({"action": "deprecated", "state": str(path), "contract": contract}, args.json)


def command_resume_set(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    role_discipline(args.role)
    data, _ = load_state(root)
    record: dict[str, Any] = {
        "capability": capability,
        "role": args.role,
        "summary": args.summary,
        "next_step": args.next_step,
        "updated_at": utc_now(),
    }
    if args.blocker:
        record["blocker"] = args.blocker
    if args.reference:
        record["references"] = unique(args.reference)
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


def command_module_complete(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    capability = validate_id(args.capability, "capability")
    contract_ids = unique(args.contract or [])
    completion_evidence = unique(nonempty(args.verification))
    if not completion_evidence:
        raise VTeamError("模块完成必须提供一条非空验证证据")
    data, _ = load_state(root)
    for contract_id in contract_ids:
        validate_id(contract_id, "contract id")
        contract = find_contract(data, contract_id)
        if contract.get("capability") != capability:
            raise VTeamError(f"契约 {contract_id} 不属于 capability {capability}")
        if contract.get("status") not in INTEGRATION_STATUSES:
            raise VTeamError(
                f"契约 {contract_id} 状态为 {contract.get('status')}，"
                "模块完成前必须是 ready 或 verified"
            )
    completed = {
        "status": "completed",
        "summary": args.summary,
        "contracts": contract_ids,
        "verification": completion_evidence,
        "completed_at": utc_now(),
    }
    data["capabilities"][capability] = completed
    cleared_active = data["active"].pop(capability, None) is not None
    path = save_state(root, data)
    emit(
        {
            "action": "module-complete",
            "state": str(path),
            "capability": capability,
            "completed": completed,
            "cleared_active": cleared_active,
        },
        args.json,
    )


def command_milestone_record(args: argparse.Namespace) -> None:
    root = project_root_from(args.project_root)
    milestone_id = validate_id(args.id, "milestone id")
    capability = validate_id(args.capability, "capability")
    data, _ = load_state(root)
    if any(item.get("id") == milestone_id for item in data["milestones"]):
        raise VTeamError(f"里程碑已存在: {milestone_id}")
    milestone = {
        "id": milestone_id,
        "capability": capability,
        "summary": args.summary,
        "references": unique(args.reference),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="V-Team capability 状态与跨角色契约索引（普通任务无需使用）"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    context_parser = commands.add_parser("context", help="读取当前角色的最小上下文")
    add_project_argument(context_parser)
    context_parser.add_argument("--role-id", required=True)
    context_parser.add_argument("--capability")
    add_json_argument(context_parser)
    context_parser.set_defaults(handler=command_context)

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

    module_parser = commands.add_parser("module", help="记录模块当前完成事实")
    module_commands = module_parser.add_subparsers(dest="module_command", required=True)
    complete = module_commands.add_parser("complete", help="完成模块并清除恢复状态")
    add_project_argument(complete)
    complete.add_argument("--capability", required=True)
    complete.add_argument("--summary", required=True)
    complete.add_argument("--verification", action="append", required=True)
    complete.add_argument("--contract", action="append")
    add_json_argument(complete)
    complete.set_defaults(handler=command_module_complete)

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
