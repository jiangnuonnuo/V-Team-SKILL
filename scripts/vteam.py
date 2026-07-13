"""description: 为 Codex 与 Claude 多 Agent 项目生成约束、身份和活动计划文件。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Sequence


SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES_ROOT = SKILL_ROOT / "references"
VALID_RUNTIMES = {"codex", "claude"}
TEMPLATE_MARKER_PATTERN = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def write_text(path: Path, content: str, overwrite: bool = True) -> None:
    """description: 以统一编码和换行写入文本文件。

    Args:
        path: 目标文件路径。
        content: 需要写入的完整文本。
        overwrite: 文件存在时是否覆盖。

    Returns:
        None。

    Raises:
        OSError: 创建目录或写入文件失败。
    """
    if path.exists() and not overwrite:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_content = content.rstrip() + "\n"
    path.write_text(normalized_content, encoding="utf-8", newline="\n")


def render_template(template_name: str, values: dict[str, str]) -> str:
    """description: 渲染技能 references 目录中的文本模板。

    Args:
        template_name: references 目录下的模板文件名。
        values: 模板标记与替换文本的映射，不包含花括号。

    Returns:
        已替换全部声明标记的模板文本。

    Raises:
        FileNotFoundError: 模板文件不存在。
        ValueError: 渲染后仍存在未替换标记。
        OSError: 模板读取失败。
    """
    template_path = REFERENCES_ROOT / template_name
    content = template_path.read_text(encoding="utf-8")

    for key, value in values.items():
        marker = "{{" + key + "}}"
        content = content.replace(marker, value)

    unresolved_markers = TEMPLATE_MARKER_PATTERN.findall(content)
    if unresolved_markers:
        marker_text = ", ".join(sorted(set(unresolved_markers)))
        raise ValueError(f"模板 {template_name} 存在未替换标记: {marker_text}")

    return content


def normalize_runtime_values(runtimes: Sequence[str]) -> list[str]:
    """description: 校验运行端并按首次出现顺序去重。

    Args:
        runtimes: Codex 或 Claude 运行端名称序列。

    Returns:
        去重后的合法运行端列表。

    Raises:
        ValueError: 运行端为空或包含不支持的值。
    """
    normalized: list[str] = []
    for raw_runtime in runtimes:
        runtime = raw_runtime.strip().lower()
        if runtime not in VALID_RUNTIMES:
            raise ValueError(f"不支持的 runtime: {raw_runtime}")
        if runtime not in normalized:
            normalized.append(runtime)

    if not normalized:
        raise ValueError("至少需要一个 runtime: codex 或 claude")

    return normalized


def normalize_relative_path(raw_path: str) -> str:
    """description: 把输入路径转换为安全的 Git 风格项目相对路径。

    Args:
        raw_path: Git 返回或用户提供的项目相对路径。

    Returns:
        使用正斜杠的项目相对路径；根规则返回点号，目录保留结尾斜杠。

    Raises:
        ValueError: 路径为空、为绝对路径、包含盘符或尝试逃逸项目根目录。
    """
    path_text = raw_path.strip().replace("\\", "/")
    if not path_text:
        raise ValueError("配置路径不能为空")
    if path_text.startswith("/") or re.match(r"^[A-Za-z]:", path_text):
        raise ValueError(f"配置路径必须是项目相对路径: {raw_path}")

    if path_text in {".", "./"}:
        return "."

    keep_trailing_slash = path_text.endswith("/")
    segments: list[str] = []
    for segment in path_text.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            raise ValueError(f"配置路径不能逃逸项目根目录: {raw_path}")
        segments.append(segment)

    if not segments:
        raise ValueError(f"配置路径不能为空: {raw_path}")

    normalized = "/".join(segments)
    if keep_trailing_slash:
        normalized += "/"
    return normalized


def normalize_config_path(raw_path: str) -> str:
    """description: 规范化 team.json 中的模块、白名单或协作文档路径。

    Args:
        raw_path: 用户提供的项目相对路径或白名单规则。

    Returns:
        安全的 Git 风格项目相对路径。

    Raises:
        ValueError: 路径为空、为绝对路径、包含盘符或尝试路径逃逸。
    """
    return normalize_relative_path(raw_path)


def decode_git_path(raw_path: str) -> str:
    """description: 解码 Git 默认输出中的 C 风格引号与八进制 UTF-8 字节。

    Args:
        raw_path: `git diff --name-only HEAD` 输出的一行路径。

    Returns:
        可直接规范化和匹配的 Unicode 路径。

    Raises:
        ValueError: 引号路径包含无效转义或字节不是合法 UTF-8。
    """
    if not raw_path.startswith('"') or not raw_path.endswith('"'):
        return raw_path

    content = raw_path[1:-1]
    decoded_bytes = bytearray()
    simple_escapes = {
        "a": 7,
        "b": 8,
        "t": 9,
        "n": 10,
        "v": 11,
        "f": 12,
        "r": 13,
        '"': 34,
        "\\": 92,
    }

    index = 0
    while index < len(content):
        character = content[index]
        if character != "\\":
            decoded_bytes.extend(character.encode("utf-8"))
            index += 1
            continue

        index += 1
        if index >= len(content):
            raise ValueError(f"Git 路径包含不完整转义: {raw_path}")

        escaped = content[index]
        if escaped in simple_escapes:
            decoded_bytes.append(simple_escapes[escaped])
            index += 1
            continue

        if escaped in "01234567":
            octal_digits = escaped
            index += 1
            while index < len(content) and len(octal_digits) < 3:
                if content[index] not in "01234567":
                    break
                octal_digits += content[index]
                index += 1
            decoded_bytes.append(int(octal_digits, 8))
            continue

        decoded_bytes.extend(escaped.encode("utf-8"))
        index += 1

    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Git 路径不是有效 UTF-8: {raw_path}") from error


def glob_to_regex(pattern: str) -> str:
    """description: 把有限 Git 风格 glob 转换为不会跨错目录层级的正则表达式。

    Args:
        pattern: 已规范化且包含星号或问号的白名单规则。

    Returns:
        可用于整串匹配的正则表达式文本。

    Raises:
        无。
    """
    parts: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                parts.append(".*")
                index += 2
            else:
                parts.append("[^/]*")
                index += 1
            continue
        if character == "?":
            parts.append("[^/]")
            index += 1
            continue
        parts.append(re.escape(character))
        index += 1
    parts.append("$")
    return "".join(parts)


def path_is_allowed(
    path: str,
    patterns: Sequence[str],
    case_sensitive: bool | None = None,
) -> bool:
    """description: 判断单个 Git 变更路径是否属于 Agent 永久白名单。

    Args:
        path: 需要检查的项目相对路径。
        patterns: 精确文件、结尾斜杠目录、glob 或点号根规则列表。
        case_sensitive: 显式大小写策略；为空时 Windows 不敏感，其他系统敏感。

    Returns:
        任一规则匹配时返回 True，否则返回 False。

    Raises:
        ValueError: 变更路径或白名单规则不是安全的项目相对路径。
    """
    normalized_path = normalize_relative_path(path)
    use_case_sensitive = os.name != "nt" if case_sensitive is None else case_sensitive
    comparable_path = normalized_path if use_case_sensitive else normalized_path.casefold()

    for raw_pattern in patterns:
        normalized_pattern = normalize_relative_path(raw_pattern)
        comparable_pattern = (
            normalized_pattern
            if use_case_sensitive
            else normalized_pattern.casefold()
        )

        if comparable_pattern == ".":
            return True
        if comparable_pattern.endswith("/"):
            if comparable_path.startswith(comparable_pattern):
                return True
            continue
        if "*" in comparable_pattern or "?" in comparable_pattern:
            if re.fullmatch(glob_to_regex(comparable_pattern), comparable_path):
                return True
            continue
        if comparable_path == comparable_pattern:
            return True

    return False


def collect_git_changes(project_root: Path) -> list[str]:
    """description: 统一读取当前本地提交相对 HEAD 涉及的全部路径。

    Args:
        project_root: 已初始化 Git 仓库的项目根目录。

    Returns:
        已解码、规范化并去除空行的变更路径列表。

    Raises:
        RuntimeError: Git 命令失败。
        ValueError: Git 返回不安全或不可解码的路径。
        OSError: Git 无法启动。
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        error_message = result.stderr.strip() or "git diff 执行失败"
        raise RuntimeError(error_message)

    changed_paths: list[str] = []
    for output_line in result.stdout.splitlines():
        if not output_line.strip():
            continue
        decoded_path = decode_git_path(output_line.strip())
        changed_paths.append(normalize_relative_path(decoded_path))
    return changed_paths


def check_scope(project_root: Path, agent_id: str) -> list[str]:
    """description: 检查一次当前 Git 变更是否全部属于指定 Agent 白名单。

    Args:
        project_root: 包含 Git 仓库和 Plan/team.json 的项目根目录。
        agent_id: 需要执行本地提交的 Agent ID。

    Returns:
        不在永久白名单内的全部变更路径。

    Raises:
        ValueError: Agent ID 不存在或配置、路径无效。
        RuntimeError: Git 差异读取失败。
        OSError: 配置或 Git 读取失败。
    """
    normalized_agent_id = validate_agent_id(agent_id)
    team = load_team(project_root)

    matching_agent: dict[str, object] | None = None
    for agent in team["agents"]:
        if agent["id"] == normalized_agent_id:
            matching_agent = agent
            break
    if matching_agent is None:
        raise ValueError(f"team.json 中不存在 agent-id: {normalized_agent_id}")

    changed_paths = collect_git_changes(project_root)
    whitelist = matching_agent["write_whitelist"]
    return [
        path
        for path in changed_paths
        if not path_is_allowed(path, whitelist)
    ]


def parse_markdown_row(line: str, expected_cells: int) -> list[str] | None:
    """description: 解析固定列数的 Markdown 表格数据行。

    Args:
        line: 可能属于表格的一整行文本。
        expected_cells: 业务表格要求的列数。

    Returns:
        数据单元格列表；非表格行、表头或分隔行返回 None。

    Raises:
        ValueError: 行是 Markdown 表格但列数不符合约定。
    """
    stripped_line = line.strip()
    if not stripped_line.startswith("|") or not stripped_line.endswith("|"):
        return None

    cells = [cell.strip() for cell in stripped_line[1:-1].split("|")]
    if all(not cell or set(cell) <= {"-", ":"} for cell in cells):
        return None
    if cells and cells[0] in {"ID", "Id", "id"}:
        return None
    if len(cells) != expected_cells:
        raise ValueError(
            f"Markdown 表格列数错误，预期 {expected_cells} 列，实际 {len(cells)} 列: {line}"
        )
    return cells


def extract_markdown_section(content: str, heading: str) -> str:
    """description: 提取二级标题下直到下一个标题前的当前内容。

    Args:
        content: 完整 Markdown 文本。
        heading: 不含井号的二级标题名称。

    Returns:
        去除首尾空白的段落文本；标题不存在时返回空字符串。

    Raises:
        无。
    """
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if match is None:
        return ""
    return match.group("body").strip()


def read_plan_state(plan_path: Path) -> dict[str, object]:
    """description: 解析个人活动计划的状态、审批、任务证据和放弃原因。

    Args:
        plan_path: `Plan/agents/<agent-id>/PLAN.md` 文件路径。

    Returns:
        包含原文、状态、审批、任务列表和放弃原因的字典。

    Raises:
        FileNotFoundError: 活动计划不存在。
        ValueError: 必需元数据、任务表或表格格式无效。
        OSError: 文件读取失败。
    """
    if not plan_path.is_file():
        raise FileNotFoundError(f"缺少活动计划: {plan_path}")
    content = plan_path.read_text(encoding="utf-8")

    status_match = re.search(r"^- Status:\s*`([^`]+)`\s*$", content, re.MULTILINE)
    if status_match is None:
        raise ValueError("PLAN.md 缺少 `- Status: `<status>`` 元数据")
    approval_match = re.search(
        r"^- Approval:\s*`([^`]+)`\s*$",
        content,
        re.MULTILINE,
    )
    if approval_match is None:
        raise ValueError("PLAN.md 缺少 `- Approval: `<status>`` 元数据")

    task_heading = "| ID | 完整功能或明确修复 | 状态 | 测试结果 | 本地提交 |"
    if task_heading not in content:
        raise ValueError("PLAN.md 缺少固定功能任务表头")

    task_section = extract_markdown_section(content, "功能任务")
    tasks: list[dict[str, str]] = []
    for line_number, line in enumerate(task_section.splitlines(), start=1):
        try:
            cells = parse_markdown_row(line, 5)
        except ValueError as error:
            raise ValueError(f"PLAN.md 功能任务表第 {line_number} 行错误: {error}") from error
        if cells is None:
            continue
        tasks.append(
            {
                "id": cells[0],
                "summary": cells[1],
                "status": cells[2],
                "test_result": cells[3],
                "commit": cells[4],
            }
        )

    reason_section = extract_markdown_section(content, "放弃原因")
    reason_lines = [
        line.strip().removeprefix("-").strip()
        for line in reason_section.splitlines()
        if line.strip()
    ]
    abandoned_reason = " ".join(reason_lines).strip()
    if abandoned_reason in {"-", "无", "无。"}:
        abandoned_reason = ""

    return {
        "content": content,
        "status": status_match.group(1).strip(),
        "approval": approval_match.group(1).strip(),
        "tasks": tasks,
        "abandoned_reason": abandoned_reason,
    }


def parse_handoff_rows(handoffs_text: str) -> list[dict[str, str]]:
    """description: 解析活动 handoff 表格中的业务数据行。

    Args:
        handoffs_text: `Plan/collaboration/handoffs.md` 完整文本。

    Returns:
        包含 ID、参与者、交付物、验收条件、状态和原行的字典列表。

    Raises:
        ValueError: handoff 表格行列数不符合固定格式。
    """
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(handoffs_text.splitlines(), start=1):
        try:
            cells = parse_markdown_row(line, 6)
        except ValueError as error:
            raise ValueError(f"handoffs.md 第 {line_number} 行错误: {error}") from error
        if cells is None:
            continue
        rows.append(
            {
                "id": cells[0],
                "proposer": cells[1],
                "receiver": cells[2],
                "deliverable": cells[3],
                "acceptance": cells[4],
                "status": cells[5],
                "raw_line": line.strip(),
            }
        )
    return rows


def validate_cleanup_state(
    plan_state: dict[str, object],
    handoffs_text: str,
    agent_id: str,
) -> None:
    """description: 校验计划状态、完成证据和跨 Agent 依赖满足清理条件。

    Args:
        plan_state: `read_plan_state` 返回的活动计划事实。
        handoffs_text: 当前活动 handoff 文本。
        agent_id: 正在清理计划的 Agent ID。

    Returns:
        None。

    Raises:
        ValueError: 计划仍活动、审批或证据不完整、放弃原因缺失、存在未关闭依赖。
    """
    status = plan_state["status"]
    if status not in {"completed", "abandoned"}:
        raise ValueError(
            f"计划状态 {status} 仍是活动状态，只允许清理 completed 或 abandoned 计划"
        )

    tasks = plan_state["tasks"]
    if status == "completed":
        if plan_state["approval"] != "approved":
            raise ValueError("completed 计划缺少 approved 用户审批记录")
        if not tasks:
            raise ValueError("completed 计划至少需要一个完整功能或明确修复任务")
        unfinished_task_ids = [
            task["id"]
            for task in tasks
            if task["status"] != "completed"
        ]
        if unfinished_task_ids:
            joined_ids = ", ".join(unfinished_task_ids)
            raise ValueError(f"completed 计划仍有未完成任务: {joined_ids}")

    if status == "abandoned" and not plan_state["abandoned_reason"]:
        raise ValueError("abandoned 计划必须记录非空放弃原因")

    commit_pattern = re.compile(r"^[0-9a-fA-F]{7,40}$")
    for task in tasks:
        if task["status"] != "completed":
            continue
        if task["test_result"] in {"", "-"}:
            raise ValueError(f"已完成任务 {task['id']} 缺少测试结果")
        if commit_pattern.fullmatch(task["commit"]) is None:
            raise ValueError(f"已完成任务 {task['id']} 缺少有效本地提交哈希")

    valid_handoff_statuses = {"open", "in-progress", "completed", "cancelled"}
    active_statuses = {"open", "in-progress"}
    for handoff in parse_handoff_rows(handoffs_text):
        if handoff["status"] not in valid_handoff_statuses:
            raise ValueError(
                f"对接 {handoff['id']} 使用未知状态: {handoff['status']}"
            )
        involves_agent = agent_id in {
            handoff["proposer"],
            handoff["receiver"],
        }
        if involves_agent and handoff["status"] in active_statuses:
            raise ValueError(
                f"存在当前 Agent 参与的未关闭对接 {handoff['id']}: {handoff['status']}"
            )


def next_archive_path(archive_root: Path, agent_id: str, date_text: str) -> Path:
    """description: 生成不会覆盖已有完成证据的确定性归档路径。

    Args:
        archive_root: 项目 `Plan/archive` 目录。
        agent_id: 被归档计划的 Agent ID。
        date_text: ISO 日期文本。

    Returns:
        首个不存在的 `<date>-<agent-id>-plan[-N].md` 路径。

    Raises:
        ValueError: Agent ID 不安全。
    """
    normalized_agent_id = validate_agent_id(agent_id)
    first_candidate = archive_root / f"{date_text}-{normalized_agent_id}-plan.md"
    if not first_candidate.exists():
        return first_candidate

    suffix = 2
    while True:
        candidate = archive_root / f"{date_text}-{normalized_agent_id}-plan-{suffix}.md"
        if not candidate.exists():
            return candidate
        suffix += 1


def remove_closed_handoffs(handoffs_text: str) -> tuple[str, list[str]]:
    """description: 从活动 handoff 表移除已完成或已取消事项。

    Args:
        handoffs_text: 当前 handoffs.md 完整文本。

    Returns:
        精简后的活动文本，以及移除行的原始摘要列表。

    Raises:
        ValueError: 表格格式错误。
    """
    closed_statuses = {"completed", "cancelled"}
    closed_rows = {
        handoff["raw_line"]
        for handoff in parse_handoff_rows(handoffs_text)
        if handoff["status"] in closed_statuses
    }
    active_lines = [
        line
        for line in handoffs_text.splitlines()
        if line.strip() not in closed_rows
    ]
    active_text = "\n".join(active_lines).rstrip() + "\n"
    return active_text, sorted(closed_rows)


def cleanup_agent_plan(project_root: Path, agent_id: str) -> Path:
    """description: 归档完成或废弃计划，重置活动计划并清理关闭的 handoff。

    Args:
        project_root: 已初始化的 V-Team 项目根目录。
        agent_id: 需要清理活动计划的 Agent ID。

    Returns:
        新生成的归档文件路径。

    Raises:
        FileNotFoundError: 个人计划或 handoff 文档不存在。
        ValueError: Agent 不存在、计划或协作状态不满足清理条件。
        OSError: 文件读取或写入失败。
    """
    normalized_agent_id = validate_agent_id(agent_id)
    team = load_team(project_root)
    registered_ids = {agent["id"] for agent in team["agents"]}
    if normalized_agent_id not in registered_ids:
        raise ValueError(f"team.json 中不存在 agent-id: {normalized_agent_id}")

    plan_path = (
        project_root
        / "Plan"
        / "agents"
        / normalized_agent_id
        / "PLAN.md"
    )
    handoffs_path = project_root / "Plan" / "collaboration" / "handoffs.md"
    if not handoffs_path.is_file():
        raise FileNotFoundError(f"缺少协作文档: {handoffs_path}")

    plan_state = read_plan_state(plan_path)
    handoffs_text = handoffs_path.read_text(encoding="utf-8")
    validate_cleanup_state(plan_state, handoffs_text, normalized_agent_id)
    active_handoffs, closed_handoffs = remove_closed_handoffs(handoffs_text)

    # 先写入新归档，任何后续失败都不会丢失原计划证据。
    archive_root = project_root / "Plan" / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    archived_on = date.today().isoformat()
    archive_path = next_archive_path(
        archive_root,
        normalized_agent_id,
        archived_on,
    )
    closed_summary = "\n".join(closed_handoffs) if closed_handoffs else "- 无。"
    archive_content = (
        f"# {normalized_agent_id} 计划归档\n\n"
        f"- Archived on: `{archived_on}`\n"
        f"- Final status: `{plan_state['status']}`\n\n"
        "## 活动计划快照\n\n"
        f"{plan_state['content'].rstrip()}\n\n"
        "## 本次移除的已关闭对接\n\n"
        f"{closed_summary}\n"
    )
    write_text(archive_path, archive_content, overwrite=False)

    reset_plan = render_template(
        "plan-template.md",
        {"AGENT_ID": normalized_agent_id},
    )
    write_text(plan_path, reset_plan)
    write_text(handoffs_path, active_handoffs)
    return archive_path


def validate_agent_id(agent_id: str) -> str:
    """description: 校验 Agent ID 可以安全用作单级目录名。

    Args:
        agent_id: 用户指定的 Agent 唯一身份。

    Returns:
        去除首尾空白后的 Agent ID。

    Raises:
        ValueError: ID 为空、为点目录或包含路径分隔符。
    """
    normalized = agent_id.strip()
    if not normalized:
        raise ValueError("agent-id 不能为空")
    if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
        raise ValueError(f"agent-id 不能包含路径分隔符: {agent_id}")
    return normalized


def validate_team(team: dict[str, object]) -> None:
    """description: 校验 team.json 顶层结构与每个 Agent 的必需字段。

    Args:
        team: 解析后的团队配置对象。

    Returns:
        None。

    Raises:
        ValueError: 必需字段缺失、类型错误、值非法或 Agent ID 重复。
    """
    if not isinstance(team, dict):
        raise ValueError("team.json 顶层必须是 JSON 对象")

    project_name = team.get("project_name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ValueError("team.json 字段 project_name 必须是非空字符串")

    runtimes = team.get("runtimes")
    if not isinstance(runtimes, list):
        raise ValueError("team.json 字段 runtimes 必须是数组")
    if any(not isinstance(runtime, str) for runtime in runtimes):
        raise ValueError("team.json 字段 runtimes 只能包含字符串")
    normalized_runtimes = normalize_runtime_values(runtimes)
    if normalized_runtimes != runtimes:
        raise ValueError("team.json 字段 runtimes 包含重复值或非规范值")

    agents = team.get("agents")
    if not isinstance(agents, list):
        raise ValueError("team.json 字段 agents 必须是数组")

    seen_agent_ids: set[str] = set()
    required_fields = {
        "id": str,
        "runtime": str,
        "role": str,
        "responsibility": str,
        "modules": list,
        "write_whitelist": list,
        "collaboration_docs": list,
    }
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            raise ValueError(f"team.json 字段 agents[{index}] 必须是对象")
        for field_name, expected_type in required_fields.items():
            field_value = agent.get(field_name)
            if not isinstance(field_value, expected_type):
                raise ValueError(
                    f"team.json 字段 agents[{index}].{field_name} 类型错误"
                )

        agent_id = validate_agent_id(agent["id"])
        if agent_id in seen_agent_ids:
            raise ValueError(f"team.json 存在重复 agent id: {agent_id}")
        seen_agent_ids.add(agent_id)

        if agent["runtime"] not in VALID_RUNTIMES:
            raise ValueError(
                f"team.json 字段 agents[{index}].runtime 值非法: {agent['runtime']}"
            )

        for list_field in ["modules", "write_whitelist", "collaboration_docs"]:
            list_value = agent[list_field]
            if any(not isinstance(item, str) for item in list_value):
                raise ValueError(
                    f"team.json 字段 agents[{index}].{list_field} 只能包含字符串"
                )
            for item in list_value:
                normalize_config_path(item)


def load_team(project_root: Path) -> dict[str, object]:
    """description: 读取并校验项目团队配置。

    Args:
        project_root: 包含 Plan/team.json 的项目根目录。

    Returns:
        已通过结构校验的团队配置对象。

    Raises:
        FileNotFoundError: team.json 不存在。
        ValueError: JSON 无法解析或配置结构错误。
        OSError: 文件读取失败。
    """
    team_path = project_root / "Plan" / "team.json"
    if not team_path.is_file():
        raise FileNotFoundError(f"缺少团队配置: {team_path}")

    try:
        team = json.loads(team_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"team.json JSON 格式错误，第 {error.lineno} 行第 {error.colno} 列"
        ) from error

    validate_team(team)
    return team


def save_team(project_root: Path, team: dict[str, object]) -> None:
    """description: 校验并保存项目团队配置。

    Args:
        project_root: 项目根目录。
        team: 需要保存的完整团队配置。

    Returns:
        None。

    Raises:
        ValueError: 配置结构无效。
        OSError: 文件写入失败。
    """
    validate_team(team)
    content = json.dumps(team, ensure_ascii=False, indent=2)
    write_text(project_root / "Plan" / "team.json", content)


def format_markdown_list(values: Sequence[str]) -> str:
    """description: 把配置值渲染为 Markdown 列表。

    Args:
        values: 需要展示的文本序列。

    Returns:
        每行一个反引号条目的 Markdown 文本；空序列返回未配置提示。

    Raises:
        无。
    """
    if not values:
        return "- （未配置）"
    return "\n".join(f"- `{value}`" for value in values)


def refresh_root_rules(project_root: Path, runtimes: Sequence[str]) -> None:
    """description: 根据项目运行端生成 Codex 或 Claude 根约束文件。

    Args:
        project_root: 项目根目录。
        runtimes: 已校验的项目运行端序列。

    Returns:
        None。

    Raises:
        FileNotFoundError: 根约束模板不存在。
        ValueError: 模板存在未替换标记。
        OSError: 模板读取或目标写入失败。
    """
    normalized_runtimes = normalize_runtime_values(runtimes)
    runtime_templates = {
        "codex": ("root-agents-template.md", "AGENTS.md"),
        "claude": ("root-claude-template.md", "CLAUDE.md"),
    }

    for runtime in normalized_runtimes:
        template_name, output_name = runtime_templates[runtime]
        content = render_template(template_name, {})
        write_text(project_root / output_name, content)


def initialize_project(project_root: Path, runtimes: Sequence[str]) -> None:
    """description: 初始化无版本的多 Agent 项目管理结构。

    Args:
        project_root: 需要初始化的项目根目录。
        runtimes: 项目使用的 Codex、Claude 运行端序列。

    Returns:
        None。

    Raises:
        ValueError: 运行端或已有团队配置无效。
        OSError: 目录或文件创建失败。
    """
    normalized_runtimes = normalize_runtime_values(runtimes)
    project_root.mkdir(parents=True, exist_ok=True)

    # 先创建固定目录，确保任何 Agent 都使用相同的无版本结构。
    plan_root = project_root / "Plan"
    (plan_root / "agents").mkdir(parents=True, exist_ok=True)
    (plan_root / "collaboration").mkdir(parents=True, exist_ok=True)
    (plan_root / "archive").mkdir(parents=True, exist_ok=True)

    team_path = plan_root / "team.json"
    if team_path.exists():
        team = load_team(project_root)
        existing_runtimes = team["runtimes"]
        team["runtimes"] = normalize_runtime_values(
            [*existing_runtimes, *normalized_runtimes]
        )
    else:
        team_content = render_template(
            "team-template.json",
            {
                "PROJECT_NAME_JSON": json.dumps(
                    project_root.name,
                    ensure_ascii=False,
                ),
                "RUNTIMES_JSON": json.dumps(
                    normalized_runtimes,
                    ensure_ascii=False,
                ),
            },
        )
        team = json.loads(team_content)

    save_team(project_root, team)

    # 当前态文档只在缺失时创建，避免重复初始化覆盖真实项目进度。
    initial_files = {
        plan_root / "project.md": "project-template.md",
        plan_root / "collaboration" / "architecture.md": "architecture-template.md",
        plan_root / "collaboration" / "api-contracts.md": "api-contracts-template.md",
        plan_root / "collaboration" / "handoffs.md": "handoffs-template.md",
    }
    for output_path, template_name in initial_files.items():
        write_text(output_path, render_template(template_name, {}), overwrite=False)

    refresh_root_rules(project_root, team["runtimes"])


def upsert_agent(
    project_root: Path,
    agent_id: str,
    runtime: str,
    role: str,
    responsibility: str,
    modules: Sequence[str],
    write_whitelist: Sequence[str],
    collaboration_docs: Sequence[str],
) -> None:
    """description: 新增或更新 Agent 身份事实与个人约束文件。

    Args:
        project_root: 已初始化的项目根目录。
        agent_id: Agent 唯一身份，也是个人目录名。
        runtime: Agent 使用的 codex 或 claude 运行端。
        role: Agent 在项目中的角色名称。
        responsibility: Agent 的主要职责描述。
        modules: Agent 默认负责的模块路径。
        write_whitelist: 无需额外授权即可提交的路径规则。
        collaboration_docs: 当前任务可能需要读取的协作文档路径。

    Returns:
        None。

    Raises:
        FileNotFoundError: 项目尚未初始化。
        ValueError: 身份、运行端、职责或路径配置无效。
        OSError: 配置或个人文件写入失败。
    """
    normalized_agent_id = validate_agent_id(agent_id)
    normalized_runtime = normalize_runtime_values([runtime])[0]
    normalized_role = role.strip()
    normalized_responsibility = responsibility.strip()
    if not normalized_role:
        raise ValueError("role 不能为空")
    if not normalized_responsibility:
        raise ValueError("responsibility 不能为空")

    normalized_modules = [normalize_config_path(path) for path in modules]
    normalized_whitelist = [normalize_config_path(path) for path in write_whitelist]
    normalized_docs = [normalize_config_path(path) for path in collaboration_docs]
    if not normalized_whitelist:
        raise ValueError("至少需要一个 --allow 白名单路径")

    team = load_team(project_root)
    agent_config = {
        "id": normalized_agent_id,
        "runtime": normalized_runtime,
        "role": normalized_role,
        "responsibility": normalized_responsibility,
        "modules": normalized_modules,
        "write_whitelist": normalized_whitelist,
        "collaboration_docs": normalized_docs,
    }

    # 使用 Agent ID 定位更新位置，同角色 Agent 不会互相覆盖。
    agents = team["agents"]
    updated_agents: list[dict[str, object]] = []
    found_existing = False
    for existing_agent in agents:
        if existing_agent["id"] == normalized_agent_id:
            updated_agents.append(agent_config)
            found_existing = True
        else:
            updated_agents.append(existing_agent)
    if not found_existing:
        updated_agents.append(agent_config)

    team["agents"] = updated_agents
    team["runtimes"] = normalize_runtime_values(
        [*team["runtimes"], normalized_runtime]
    )
    save_team(project_root, team)

    personal_rules = render_template(
        "personal-agent-template.md",
        {
            "AGENT_ID": normalized_agent_id,
            "RUNTIME": normalized_runtime,
            "ROLE": normalized_role,
            "RESPONSIBILITY": normalized_responsibility,
            "MODULES": format_markdown_list(normalized_modules),
            "WRITE_WHITELIST": format_markdown_list(normalized_whitelist),
            "COLLABORATION_DOCS": format_markdown_list(normalized_docs),
        },
    )
    agent_root = project_root / "Plan" / "agents" / normalized_agent_id
    write_text(agent_root / "AGENT.md", personal_rules)

    plan_content = render_template(
        "plan-template.md",
        {"AGENT_ID": normalized_agent_id},
    )
    write_text(agent_root / "PLAN.md", plan_content, overwrite=False)
    refresh_root_rules(project_root, team["runtimes"])


def build_parser() -> argparse.ArgumentParser:
    """description: 构建 V-Team 命令行参数解析器。

    Args:
        无。

    Returns:
        包含 init、agent、check-scope 与 cleanup 子命令的 ArgumentParser。

    Raises:
        无。
    """
    parser = argparse.ArgumentParser(
        description="初始化和维护 Codex/Claude 多 Agent 项目约束。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化无版本 Plan 结构")
    init_parser.add_argument("--project-root", required=True, type=Path)
    init_parser.add_argument(
        "--runtime",
        required=True,
        action="append",
        choices=sorted(VALID_RUNTIMES),
    )

    agent_parser = subparsers.add_parser("agent", help="新增或更新 Agent 身份")
    agent_parser.add_argument("--project-root", required=True, type=Path)
    agent_parser.add_argument("--agent-id", required=True)
    agent_parser.add_argument(
        "--runtime",
        required=True,
        choices=sorted(VALID_RUNTIMES),
    )
    agent_parser.add_argument("--role", required=True)
    agent_parser.add_argument("--responsibility", required=True)
    agent_parser.add_argument("--module", action="append", default=[])
    agent_parser.add_argument("--allow", action="append", required=True)
    agent_parser.add_argument("--read-doc", action="append", default=[])

    scope_parser = subparsers.add_parser(
        "check-scope",
        help="本地提交前统一检查一次变更路径",
    )
    scope_parser.add_argument("--project-root", required=True, type=Path)
    scope_parser.add_argument("--agent-id", required=True)

    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="归档完成或废弃计划并重置活动上下文",
    )
    cleanup_parser.add_argument("--project-root", required=True, type=Path)
    cleanup_parser.add_argument("--agent-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """description: 解析命令并执行对应的项目维护操作。

    Args:
        argv: 不含程序名的命令行参数；为空时读取 sys.argv。

    Returns:
        0 表示成功，1 表示已知配置或文件错误。

    Raises:
        SystemExit: argparse 在参数格式错误时终止并返回标准退出码。
    """
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "init":
            initialize_project(arguments.project_root, arguments.runtime)
            print(f"项目已初始化: {arguments.project_root}")
            return 0

        if arguments.command == "agent":
            upsert_agent(
                project_root=arguments.project_root,
                agent_id=arguments.agent_id,
                runtime=arguments.runtime,
                role=arguments.role,
                responsibility=arguments.responsibility,
                modules=arguments.module,
                write_whitelist=arguments.allow,
                collaboration_docs=arguments.read_doc,
            )
            print(f"Agent 已更新: {arguments.agent_id}")
            return 0

        if arguments.command == "check-scope":
            violations = check_scope(
                project_root=arguments.project_root,
                agent_id=arguments.agent_id,
            )
            if not violations:
                print(f"范围检查通过: {arguments.agent_id}")
                return 0

            print(f"发现白名单外路径，Agent: {arguments.agent_id}", file=sys.stderr)
            for violation in violations:
                print(f"- {violation}", file=sys.stderr)
            print(
                "暂停当前本地提交；请向用户说明修改原因和影响，并询问是否允许本次提交。",
                file=sys.stderr,
            )
            print(
                "用户同意后只在当前 PLAN.md 记录一次性授权；该授权不会扩大永久白名单。",
                file=sys.stderr,
            )
            return 2

        if arguments.command == "cleanup":
            archive_path = cleanup_agent_plan(
                project_root=arguments.project_root,
                agent_id=arguments.agent_id,
            )
            print(f"计划已归档并重置: {archive_path}")
            return 0
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1

    print(f"错误: 未支持的命令 {arguments.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
