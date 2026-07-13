# V-Team 多 Agent 协作技能重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `project-harness-lite` 重构为支持 Codex/Claude、多 Agent 模块边界、单份审批计划、提交前白名单检查、当前态协作文档和安全归档清理的跨平台团队开发技能。

**Architecture:** 使用一个仅依赖 Python 标准库的 `scripts/vteam.py` 统一承载项目初始化、Agent 注册、提交范围检查和计划清理。项目事实保存在 `Plan/team.json`，行为约束由根目录入口文件与 `Plan/agents/<agent-id>/AGENT.md` 表达，活动状态由单份 `PLAN.md` 和三份当前态协作文档承载。

**Tech Stack:** Python 3 标准库、`argparse`、`json`、`pathlib`、`subprocess`、`unittest`、Git、Markdown。

**设计依据:** `docs/superpowers/specs/2026-07-13-v-team-skill-redesign-design.md`

**审批状态:** 用户已于 2026-07-13 通过“开始执行”确认书面设计并授权进入实现。

**执行边界:** 只在本地 `develop` 分支开发；使用中文本地提交；不推送远程、不合并分支。技能本身不包含分支创建、切换、命名或管理规则。

---

## 文件职责映射

| 文件 | 操作 | 单一职责 |
|---|---|---|
| `scripts/vteam.py` | 新建 | 四个子命令的统一跨平台入口、配置校验、路径匹配和归档清理 |
| `tests/test_vteam.py` | 新建 | 对 CLI、文件生成、白名单和清理行为做端到端临时目录测试 |
| `references/root-agents-template.md` | 新建 | Codex 项目根目录 `AGENTS.md` 模板 |
| `references/root-claude-template.md` | 新建 | Claude 项目根目录 `CLAUDE.md` 模板 |
| `references/personal-agent-template.md` | 新建 | 个人身份、白名单、计划与协作规则模板 |
| `references/plan-template.md` | 新建 | 单份活动计划模板 |
| `references/project-template.md` | 新建 | 项目当前目标、模块边界和当前阶段模板 |
| `references/architecture-template.md` | 新建 | 当前有效架构模板 |
| `references/api-contracts-template.md` | 新建 | 当前有效接口契约模板 |
| `references/handoffs-template.md` | 新建 | 未关闭跨 Agent 对接事项模板 |
| `references/team-template.json` | 新建 | `team.json` 初始结构示例 |
| `SKILL.md` | 重写 | 技能触发条件、核心强制规则、工作流和命令说明 |
| `agents/openai.yaml` | 修改 | Codex 技能列表展示信息与默认提示词 |
| `README.md` | 新建 | 仓库使用说明、目录结构、命令示例和约束摘要 |
| `F:/java/code/SKILLS/README.md` | 修改 | 技能库索引中的用途说明 |
| 旧 `scripts/*.py` 与旧 `references/*.md` | 删除 | 移除版本制、经理周期和旧角色卡实现，不保留兼容层 |

## 固定数据与命令契约

`Plan/team.json` 使用下面的稳定结构，不引入项目版本字段：

```json
{
  "project_name": "example-project",
  "runtimes": ["codex"],
  "agents": [
    {
      "id": "backend-1",
      "runtime": "codex",
      "role": "backend",
      "responsibility": "用户与权限后端",
      "modules": ["backend/auth"],
      "write_whitelist": ["backend/auth/", "tests/auth/"],
      "collaboration_docs": ["Plan/collaboration/api-contracts.md"]
    }
  ]
}
```

CLI 契约：

```text
python scripts/vteam.py init --project-root <path> --runtime codex [--runtime claude]
python scripts/vteam.py agent --project-root <path> --agent-id <id> --runtime <codex|claude> --role <role> --responsibility <text> --module <path> --allow <path> [--read-doc <path>]
python scripts/vteam.py check-scope --project-root <path> --agent-id <id>
python scripts/vteam.py cleanup --project-root <path> --agent-id <id>
```

初始化后的固定当前态文件为 `Plan/project.md`、`Plan/team.json`、`Plan/collaboration/architecture.md`、`Plan/collaboration/api-contracts.md` 和 `Plan/collaboration/handoffs.md`。这些文件优先覆盖或修订现状，不为新对话复制新文件；完成或废弃历史进入 `Plan/archive/` 并由根入口规则默认忽略。

`check-scope` 返回码固定为：`0` 表示全部在白名单内，`2` 表示发现白名单外路径，`1` 表示配置、Git 或输入错误。一次性授权只记录在 `PLAN.md`，绝不写回 `team.json`。

---

### Task 1: 项目初始化与 Agent 身份约束生成

**功能提交:** 初始化无版本 `Plan/` 结构；按运行端生成根约束；新增或更新 Agent 时生成独立 `AGENT.md`、`PLAN.md` 并同步 `team.json`。

**Files:**
- Create: `scripts/vteam.py`
- Create: `tests/test_vteam.py`
- Create: `references/root-agents-template.md`
- Create: `references/root-claude-template.md`
- Create: `references/personal-agent-template.md`
- Create: `references/plan-template.md`
- Create: `references/project-template.md`
- Create: `references/architecture-template.md`
- Create: `references/api-contracts-template.md`
- Create: `references/handoffs-template.md`
- Create: `references/team-template.json`

- [x] **实现并验证“初始化与 Agent 注册”完整功能，形成一次中文本地提交**

测试先行，先在 `tests/test_vteam.py` 建立 `VTeamTestCase`。每个测试使用 `tempfile.TemporaryDirectory()`，通过 `importlib.util.spec_from_file_location` 加载 `scripts/vteam.py`，不写入真实用户项目。至少实现以下测试：

| 测试方法 | 准备与断言 |
|---|---|
| `test_codex_init_creates_only_codex_root_file` | 以 `runtimes=["codex"]` 初始化，断言存在 `AGENTS.md` 且不存在 `CLAUDE.md` |
| `test_claude_init_creates_only_claude_root_file` | 以 `runtimes=["claude"]` 初始化，断言存在 `CLAUDE.md` 且不存在 `AGENTS.md` |
| `test_mixed_init_creates_both_root_files` | 以两个运行端初始化，断言两个根入口同时存在 |
| `test_init_never_creates_versions_directory` | 初始化后断言 `Plan/versions` 不存在 |
| `test_root_rules_contain_required_behavior_gates` | 读取根入口并逐条断言身份、个人规则、计划审批、测试、push/merge、归档忽略规则 |
| `test_register_agents_with_same_role_keeps_separate_identity_files` | 注册 `backend-1`、`backend-2`，断言 JSON 有两条记录且个人目录互不覆盖 |
| `test_register_agent_writes_identity_scope_and_required_reads` | 注册 Agent 后断言个人规则包含职责、模块、白名单和必读协作文档 |
| `test_register_agent_updates_runtime_root_files` | 在 Codex 项目增加 Claude Agent，断言自动生成 `CLAUDE.md` 且保留 `AGENTS.md` |
| `test_invalid_team_configuration_reports_exact_field` | 把 `agents` 改成字符串，断言抛出的 `ValueError` 明确包含 `agents` 字段名 |

失败验证命令：

```powershell
python tests/test_vteam.py InitializationTests AgentRegistrationTests -v
```

预期：因 `scripts/vteam.py` 或目标函数尚不存在而失败。

`scripts/vteam.py` 的公开接口固定如下，后续任务复用这些入口：

- `VALID_RUNTIMES = {"codex", "claude"}`：唯一合法运行端集合。
- `load_team(project_root: Path) -> dict[str, object]`：读取、解析并校验 `Plan/team.json`。
- `save_team(project_root: Path, team: dict[str, object]) -> None`：校验后以 UTF-8、两空格缩进和结尾换行写入配置。
- `validate_team(team: dict[str, object]) -> None`：校验顶层字段、运行端、Agent 唯一性、字段类型和路径安全性。
- `render_template(template_name: str, values: dict[str, str]) -> str`：读取技能内模板并替换所有已声明标记；存在未替换标记时抛出 `ValueError`。
- `initialize_project(project_root: Path, runtimes: list[str]) -> None`：创建固定目录和初始当前态文件。
- `upsert_agent(project_root: Path, agent_id: str, runtime: str, role: str, responsibility: str, modules: list[str], write_whitelist: list[str], collaboration_docs: list[str]) -> None`：新增或更新身份事实和个人规则。
- `refresh_root_rules(project_root: Path, runtimes: list[str]) -> None`：根据运行端集合生成或删除对应根入口。
- `build_parser() -> argparse.ArgumentParser`：声明四个子命令和参数。
- `main(argv: list[str] | None = None) -> int`：分发命令、把已知输入错误写到标准错误并返回稳定退出码。

实现要求：

1. `initialize_project` 创建 `Plan/agents/`、`Plan/collaboration/`、`Plan/archive/`，写入 `project.md`、`team.json` 和三份协作文档；不得创建 `Plan/versions/`。
2. `--runtime` 可重复，仅接受 `codex`、`claude`；重复值去重并保持稳定顺序。
3. 根入口文件必须原文包含：无法确定 `agent-id` 时停止并询问用户；必须读取个人 `AGENT.md`；用户批准 `PLAN.md` 前禁止实现；测试通过后才能提交；禁止自行 push/merge；默认忽略完成、废弃和归档内容。
4. `upsert_agent` 以 Agent ID 为唯一键；同角色不同 ID 必须共存；更新已有 ID 时只重写该 Agent 配置和个人 `AGENT.md`，已有非空活动 `PLAN.md` 不得覆盖。
5. 白名单和协作文档路径写入 JSON 前统一为 Git `/` 分隔相对路径，并拒绝绝对路径、盘符和 `..` 路径逃逸。
6. 所有模块、函数和关键步骤使用中文 docstring/独立行注释；函数 docstring 写清参数、返回值和异常；禁止行尾注释。

通过验证命令：

```powershell
python tests/test_vteam.py InitializationTests AgentRegistrationTests -v
```

预期：上述初始化和身份测试全部 `OK`。

提交前执行：

```powershell
git diff --name-only
git add scripts/vteam.py tests/test_vteam.py references/root-agents-template.md references/root-claude-template.md references/personal-agent-template.md references/plan-template.md references/project-template.md references/architecture-template.md references/api-contracts-template.md references/handoffs-template.md references/team-template.json
git commit -m "功能：支持项目初始化与Agent身份约束"
```

完成记录：测试结果和功能提交哈希写回本任务下方的“执行记录”，不得预填或伪造。

---

### Task 2: 本地提交前白名单检查与一次性授权提示

**功能提交:** 对 `git diff --name-only HEAD` 返回的路径做一次统一范围检查；准确报告越界路径并提示向用户申请本次提交的一次性授权，不修改永久白名单。

**Files:**
- Modify: `scripts/vteam.py`
- Modify: `tests/test_vteam.py`

- [x] **实现并验证“提交范围检查”完整功能，形成一次中文本地提交**

先新增以下测试：

| 测试方法 | 准备与断言 |
|---|---|
| `test_paths_inside_whitelist_pass` | 白名单为 `backend/`，变更为 `backend/auth/service.py`，断言越界列表为空 |
| `test_paths_outside_whitelist_are_reported` | 增加 `frontend/login.ts`，断言只返回该路径 |
| `test_backslashes_spaces_and_non_ascii_paths_are_normalized` | 输入 `后端\用户 模块\服务.py`，断言规范化为 Git `/` 路径并正确匹配 |
| `test_case_insensitive_matching_can_model_windows` | 显式传 `case_sensitive=False`，断言 `Backend/API.py` 匹配 `backend/` |
| `test_path_escape_and_absolute_paths_are_rejected` | 分别输入 `../secret`、`C:\secret`、`/tmp/secret`，断言抛出 `ValueError` |
| `test_one_time_approval_is_never_persisted_to_team_json` | 检查前后读取配置文本，断言字节内容一致且不存在授权字段 |
| `test_git_diff_uses_name_only_head_once` | mock `subprocess.run`，断言只调用一次且参数等于 `git diff --name-only HEAD` 的数组形式 |

失败验证命令：

```powershell
python tests/test_vteam.py ScopeCheckTests -v
```

预期：因下列范围检查函数尚不存在而失败。

新增接口：

- `normalize_relative_path(raw_path: str) -> str`：规范化 Git 相对路径并拒绝路径逃逸。
- `path_is_allowed(path: str, patterns: list[str], case_sensitive: bool | None = None) -> bool`：按精确、目录或 glob 规则匹配单个路径。
- `collect_git_changes(project_root: Path) -> list[str]`：只运行一次 `git diff --name-only HEAD` 并返回非空路径。
- `check_scope(project_root: Path, agent_id: str) -> list[str]`：读取 Agent 永久白名单并返回全部越界路径。

匹配规则必须明确且可测试：

- `README.md` 表示精确文件。
- `backend/` 表示该目录及全部后代。
- `backend/**` 和 `frontend/*.ts` 作为 Git 风格 glob。
- `.` 表示项目内全部路径。
- 输入先把 `\` 转成 `/`，移除重复的 `./`，拒绝绝对路径、Windows 盘符和任何 `..` 段。
- 默认根据当前系统决定大小写语义：Windows 不区分大小写，macOS 保持路径字符串的大小写；测试可以显式传入 `case_sensitive`。

`collect_git_changes` 只能使用参数数组调用：

```python
subprocess.run(
    ["git", "diff", "--name-only", "HEAD"],
    cwd=project_root,
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
```

禁止拼接 shell 字符串。`check-scope` 的越界输出必须列出 Agent ID、越界路径，并明确说明：暂停当前本地提交；向用户报告修改原因和影响；用户同意时只在当前 `PLAN.md` 记录一次性授权；该授权不会扩展 `team.json` 的永久白名单。命令本身不接受 `--approve`，避免把授权变成脚本绕过开关。

通过验证命令：

```powershell
python tests/test_vteam.py ScopeCheckTests -v
```

预期：全部 `OK`，越界场景返回码为 `2`，且再次读取 `team.json` 与检查前完全一致。

提交前执行：

```powershell
git diff --name-only
git add scripts/vteam.py tests/test_vteam.py
git commit -m "功能：增加本地提交白名单检查"
```

完成记录：测试结果和功能提交哈希写回本任务下方的“执行记录”。

---

### Task 3: 完成计划的安全归档与活动文档清理

**功能提交:** 只允许清理 `completed` 或 `abandoned` 计划；校验完成证据；归档精简快照、重置活动计划并清除已关闭 handoff。

**Files:**
- Modify: `scripts/vteam.py`
- Modify: `tests/test_vteam.py`
- Modify: `references/plan-template.md`
- Modify: `references/handoffs-template.md`

- [x] **实现并验证“计划归档与清理”完整功能，形成一次中文本地提交**

计划模板中的机器可读头部和任务表固定为：

```markdown
# <agent-id> 活动计划

- Agent ID: `<agent-id>`
- Status: `draft`
- Approval: `pending`

| ID | 完整功能或明确修复 | 状态 | 测试结果 | 本地提交 |
|---|---|---|---|---|
```

handoff 表固定为：

```markdown
| ID | 提出者 | 接收者 | 交付物 | 验收条件 | 状态 |
|---|---|---|---|---|---|
```

先新增以下测试：

| 测试方法 | 准备与断言 |
|---|---|
| `test_draft_and_in_progress_plans_cannot_be_cleaned` | 分别写入两种活动状态，断言均抛出 `ValueError` 且原文不变 |
| `test_completed_plan_requires_tasks_tests_and_commit_hashes` | 依次缺少任务、测试、哈希，断言错误准确指出缺失证据 |
| `test_abandoned_plan_can_be_archived_with_reason` | 写入放弃原因，断言能够归档；移除原因后断言拒绝 |
| `test_completed_plan_is_archived_and_active_plan_is_reset` | 写入证据完整的完成计划，断言归档保留原证据且活动计划回到空白草稿 |
| `test_closed_handoffs_are_archived_and_removed_from_active_file` | 写入 completed/cancelled 行，断言活动表移除且归档包含摘要 |
| `test_open_handoff_involving_agent_blocks_completed_cleanup` | 写入当前 Agent 参与的 open 行，断言拒绝清理 |
| `test_archive_name_collision_creates_deterministic_suffix` | 预建同日归档，断言新文件使用 `-2` 且原文件不变 |

失败验证命令：

```powershell
python tests/test_vteam.py CleanupTests -v
```

预期：因清理函数尚不存在而失败。

新增接口：

- `read_plan_state(plan_path: Path) -> dict[str, object]`：解析状态、审批、目标、放弃原因和任务表。
- `validate_cleanup_state(plan_state: dict[str, object], handoffs_text: str, agent_id: str) -> None`：校验清理状态、完成证据与未关闭协作依赖。
- `next_archive_path(archive_root: Path, agent_id: str, date_text: str) -> Path`：生成不覆盖旧文件的确定性归档路径。
- `remove_closed_handoffs(handoffs_text: str) -> tuple[str, list[str]]`：返回精简后的活动文档和已关闭行摘要。
- `cleanup_agent_plan(project_root: Path, agent_id: str) -> Path`：完成先归档、再重置、最后更新 handoff 的顺序化清理。

实现规则：

1. 解析 `Status`、`Approval` 和任务表；格式错误时给出具体字段或行号，不能把无法解析的计划当作可清理。
2. `completed` 计划至少包含一个任务，所有任务状态均为 `completed`，测试结果非空且不是 `-`，本地提交为 7 到 40 位十六进制哈希。
3. `abandoned` 计划必须存在非空的“放弃原因”；已完成任务仍需保留其测试和提交证据。
4. 涉及当前 Agent 的 `open` 或 `in-progress` handoff 会阻止正常完成计划的清理；`completed`、`cancelled` 项从活动表移除并以摘要进入同一归档快照。
5. 归档文件名使用 `<YYYY-MM-DD>-<agent-id>-plan.md`；同名时顺序使用 `-2`、`-3`，不得覆盖旧证据。
6. 归档成功后才重置 `PLAN.md`；重置后状态为 `draft`、审批为 `pending`、目标和任务为空，并明确“当前无活动任务”。
7. 任一校验或写入失败时不得删除原计划内容。写入采用 UTF-8 和 `\n`。

通过验证命令：

```powershell
python tests/test_vteam.py CleanupTests -v
```

预期：全部 `OK`；活动计划被拒绝，证据完整的完成/放弃计划安全归档。

提交前执行：

```powershell
git diff --name-only
git add scripts/vteam.py tests/test_vteam.py references/plan-template.md references/handoffs-template.md
git commit -m "功能：支持完成计划安全归档清理"
```

完成记录：测试结果和功能提交哈希写回本任务下方的“执行记录”。

---

### Task 4: 技能规则重写、旧版本制移除与技能库索引同步

**功能提交:** 让技能说明、默认提示、仓库文档、模板和技能库索引完整反映新工作流；删除旧版本制实现并通过契约扫描和全量测试。

**Files:**
- Modify: `SKILL.md`
- Modify: `agents/openai.yaml`
- Create: `README.md`
- Modify: `tests/test_vteam.py`
- Modify: `F:/java/code/SKILLS/README.md`
- Delete: `scripts/init_project.py`
- Delete: `scripts/register_agent.py`
- Delete: `scripts/run_manager_cycle.py`
- Delete: `scripts/update_agent_status.py`
- Delete: `scripts/update_review.py`
- Delete: `references/agent-card-template.md`
- Delete: `references/memory-rules.md`
- Delete: `references/next-steps-template.md`
- Delete: `references/product-report-template.md`
- Delete: `references/review-template.md`
- Delete: `references/verification-template.md`
- Delete: `references/work-template.md`

- [x] **实现并验证“技能交付契约与旧结构清理”完整功能，形成一次中文本地提交**

先在 `tests/test_vteam.py` 新增静态契约测试：

| 测试方法 | 准备与断言 |
|---|---|
| `test_skill_description_matches_multi_agent_project_workflow` | 断言 frontmatter 描述包含 Codex、Claude、多 Agent、模块边界和单份计划，不含 versioned workflow |
| `test_skill_requires_identity_personal_agent_and_plan_approval` | 断言正文明确身份未知时停止、强制个人规则、审批前禁止实现 |
| `test_skill_documents_single_pre_commit_scope_check` | 断言只在本地提交前检查一次，并明确使用 `git diff --name-only HEAD` |
| `test_skill_allows_user_approved_cross_module_commit` | 断言用户一次性授权流程和不扩展永久白名单 |
| `test_skill_forbids_remote_push_and_self_merge_without_managing_branches` | 断言禁止 push/merge，同时明确技能不创建、切换或命名分支 |
| `test_skill_documents_living_collaboration_and_cleanup_rules` | 断言三份当前态协作文档、覆盖优先、关闭事项移除和归档忽略规则 |
| `test_old_scripts_and_version_templates_are_removed` | 逐个断言旧脚本/模板不存在，并断言新入口存在 |
| `test_repository_and_library_readmes_are_updated` | 断言仓库 README 有跨平台示例，技能库索引使用新的用途文案 |

失败验证命令：

```powershell
python tests/test_vteam.py SkillContractTests -v
```

预期：旧 `SKILL.md` 仍描述 `Plan/versions/`，旧脚本仍存在，因此测试失败。

`SKILL.md` 必须线性描述以下实际执行顺序：

1. 判断项目使用 Codex、Claude 或混合运行端，运行 `init`。
2. 用户为每个 Agent 指定 ID、角色、职责、模块和写入白名单，运行 `agent`。
3. Agent 进入项目先读根入口，再强制读取自己的 `AGENT.md`；身份不明时询问用户。
4. Agent 更新唯一 `PLAN.md`，任务项只能是完整功能或明确修复；状态进入 `waiting-approval`。
5. 用户批准后进入实现；每项运行足够证明功能正确的测试。
6. 本地提交前只统一执行一次 `check-scope`，其数据来自 `git diff --name-only HEAD`。
7. 越界时报告路径、原因和影响并询问用户；用户可以只授权当前提交，Agent 在 `PLAN.md` 记录授权，不修改永久白名单。
8. 测试通过并完成范围处理后使用中文本地提交；禁止自行 push 或 merge；技能不管理分支。
9. 提交后更新任务状态、测试结果和提交哈希；所有任务完成后更新必要的架构、接口或 handoff 当前态。
10. 只在计划完成或废弃且证据满足时运行 `cleanup`；默认忽略归档和已完成内容。

仓库 `README.md` 给出 Windows 与 macOS 均可复制的命令示例，说明路径包含空格时要加引号。`agents/openai.yaml` 的 `short_description` 和 `default_prompt` 不再出现 version、manager cycle、solo role rotation。技能库根 `README.md` 的索引条目更新为：

```markdown
| project-harness-lite | Codex/Claude 多Agent协作开发约束与计划工具 | 项目管理 |
```

删除旧文件后，执行契约测试和全量测试：

```powershell
python tests/test_vteam.py SkillContractTests -v
python -m unittest discover -s tests -p "test_*.py" -v
python -m py_compile scripts/vteam.py tests/test_vteam.py
python scripts/vteam.py --help
python scripts/vteam.py init --help
python scripts/vteam.py agent --help
python scripts/vteam.py check-scope --help
python scripts/vteam.py cleanup --help
```

预期：全部测试 `OK`，编译无输出且退出码为 `0`，五条帮助命令均退出码为 `0`；仓库中不存在旧脚本和任何运行时生成的 `Plan/versions/`。

最终人工核对：

```powershell
git diff --check
git diff --name-only
git status --short
```

预期：`git diff --check` 无输出；变更文件全部属于本计划；不包含安装目录 `C:/Users/JIANG  SIR/.codex/skills/project-harness-lite`，因为是否同步安装需要用户另行确认。

提交前执行：

```powershell
git add SKILL.md agents/openai.yaml README.md tests/test_vteam.py references scripts
git commit -m "重构：完成多Agent协作开发技能"
```

注意：父目录 `F:/java/code/SKILLS/README.md` 不属于当前 Git 仓库，无法与仓库源码进入同一个提交；实际执行时先完成仓库内中文提交，再单独保留并报告技能库索引变更。如果父目录由另一个 Git 仓库管理，则在该仓库执行独立中文本地提交；不得伪造同一提交包含跨仓库文件。

完成记录：写入全量测试结果、功能提交哈希和父索引处理结果，然后将本计划整体标记为完成。

---

## 执行记录

| 功能任务 | 状态 | 测试结果 | 本地提交 | 备注 |
|---|---|---|---|---|
| Task 1 初始化与 Agent 注册 | completed | 9 项测试通过；`py_compile` 通过 | `1c25eb4` | Windows 子进程输出按平台编码验证，生成文件保持 UTF-8 |
| Task 2 提交范围检查 | completed | 9 项功能测试、18 项累计回归通过 | `59a6bc0` | 只运行一次 `git diff --name-only HEAD`；授权不落永久配置 |
| Task 3 计划归档与清理 | completed | 7 项功能测试、25 项累计回归通过 | `7c34f5b` | 归档优先；活动计划与开放对接均阻止清理 |
| Task 4 技能契约与旧结构清理 | completed | `quick_validate` 通过；35 项全量测试通过；4 个子命令帮助通过 | `7d01c1c` | 自审修复 `25fb5fe`；父技能库索引已更新，父目录无 Git 仓库 |

**整体状态:** `completed`
