"""description: 为 Codex 与 Claude 多 Agent 项目生成约束、身份和活动计划文件。"""

from __future__ import annotations

import argparse
import json
import re
import sys
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


def normalize_config_path(raw_path: str) -> str:
    """description: 把配置路径转换为安全的 Git 风格项目相对路径。

    Args:
        raw_path: 用户提供的模块、白名单或协作文档路径。

    Returns:
        使用正斜杠的项目相对路径，并保留目录结尾斜杠。

    Raises:
        ValueError: 路径为空、为绝对路径、包含盘符或尝试逃逸项目根目录。
    """
    path_text = raw_path.strip().replace("\\", "/")
    if not path_text:
        raise ValueError("配置路径不能为空")
    if path_text.startswith("/") or re.match(r"^[A-Za-z]:", path_text):
        raise ValueError(f"配置路径必须是项目相对路径: {raw_path}")

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
        包含 init 与 agent 子命令的 ArgumentParser。

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
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1

    print(f"错误: 未支持的命令 {arguments.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
