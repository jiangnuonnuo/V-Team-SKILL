# V-Team SKILL

`project-harness-lite` 是面向自用或小团队的 Codex/Claude 多 Agent 项目协作技能。它在单个项目目录内生成根约束、个人身份、模块白名单、单份活动计划和当前态协作文档，并提供提交前范围检查与安全归档清理。

## 能力

- Codex 生成 `AGENTS.md`，Claude 生成 `CLAUDE.md`，混合团队同时生成两者。
- 每个 Agent 使用独立 `Plan/agents/<agent-id>/AGENT.md` 和唯一 `PLAN.md`。
- 用户只需给出 Agent 身份和业务/项目范围；Agent 据此映射完整工作范围并生成个人约束。
- 每个计划任务保持完整功能或明确修复粒度；review 通过且用户批准后才能实现。
- `check-plan` 校验固定 review 记录，语义 review 仍由独立 Agent 完成。
- 本地提交前只运行一次 `git diff --name-only HEAD` 范围检查。
- 越界修改由用户授权当前提交，不永久扩展白名单。
- 架构、接口和 handoff 只保存当前有效协作事实。
- 完成或废弃计划采用归档优先清理，并验证完成任务记录的本地提交真实存在。
- 不推送远程、不自行合并，也不管理 Git 分支。

## 环境要求

- Python 3.9 或更高版本。
- Git 可从命令行直接执行。
- 不需要第三方 Python 包。

脚本使用 Python 标准库、`pathlib` 和参数数组调用 Git，可在 Windows 与 macOS 使用。路径包含空格时始终使用引号。若使用 Conda，先激活目标环境并用该环境的 `python` 执行；不要假定 `python3` 与当前 Conda 环境相同。

## Windows 示例

```powershell
python "F:\java\code\SKILLS\V-Team-SKILL\scripts\vteam.py" init --project-root "F:\java\code\item\example-project" --runtime codex

python "F:\java\code\SKILLS\V-Team-SKILL\scripts\vteam.py" agent --project-root "F:\java\code\item\example-project" --agent-id backend-1 --runtime codex --role backend --responsibility "用户与权限后端" --scope "用户与权限后端全部代码" --module backend/auth --allow backend/auth/ --allow tests/auth/ --read-doc Plan/collaboration/api-contracts.md

python "F:\java\code\SKILLS\V-Team-SKILL\scripts\vteam.py" check-plan --project-root "F:\java\code\item\example-project" --agent-id backend-1

python "F:\java\code\SKILLS\V-Team-SKILL\scripts\vteam.py" check-scope --project-root "F:\java\code\item\example-project" --agent-id backend-1

python "F:\java\code\SKILLS\V-Team-SKILL\scripts\vteam.py" cleanup --project-root "F:\java\code\item\example-project" --agent-id backend-1
```

## macOS 示例

```bash
python --version

python "/Users/me/skills/V-Team-SKILL/scripts/vteam.py" init --project-root "/Users/me/projects/example-project" --runtime codex --runtime claude

python "/Users/me/skills/V-Team-SKILL/scripts/vteam.py" agent --project-root "/Users/me/projects/example-project" --agent-id frontend-1 --runtime claude --role frontend --responsibility "登录页面与接口集成" --scope "用户端前端全部代码" --module frontend/auth --allow frontend/auth/ --read-doc Plan/collaboration/api-contracts.md

python "/Users/me/skills/V-Team-SKILL/scripts/vteam.py" check-plan --project-root "/Users/me/projects/example-project" --agent-id frontend-1

python "/Users/me/skills/V-Team-SKILL/scripts/vteam.py" check-scope --project-root "/Users/me/projects/example-project" --agent-id frontend-1

python "/Users/me/skills/V-Team-SKILL/scripts/vteam.py" cleanup --project-root "/Users/me/projects/example-project" --agent-id frontend-1
```

## 生成目录

```text
<project-root>/
  AGENTS.md or CLAUDE.md
  Plan/
    project.md
    onboarding.md
    team.json
    agents/<agent-id>/AGENT.md
    agents/<agent-id>/PLAN.md
    collaboration/architecture.md
    collaboration/api-contracts.md
    collaboration/handoffs.md
    archive/
```

完整规则和异常门禁见 [`SKILL.md`](SKILL.md)，模板位于 `references/`，自动化测试位于 `tests/test_vteam.py`。
