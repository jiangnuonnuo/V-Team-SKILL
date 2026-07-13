---
name: project-harness-lite
description: Use when a Codex or Claude project needs multi-agent collaboration, distinct roles, module ownership boundaries, shared current-state contracts, or recoverable project-local planning across independent agent sessions.
---

# Project Harness Lite

## 概述

在一个项目目录内组织 Codex、Claude 或混合 Agent 团队。使用 `Plan/team.json` 保存身份和永久白名单事实，使用项目根约束与个人 `AGENT.md` 强制行为边界，使用单份活动 `PLAN.md` 保持审批、测试、本地提交和恢复进度可追踪。

核心原则：先确认身份和计划，再实现；默认遵守模块归属，同时允许跨模块；只在本地提交前检查一次范围；协作文档只保留当前有效事实。

## 项目结构

初始化后使用固定结构：

```text
<project-root>/
  AGENTS.md                         # 存在 Codex Agent 时生成
  CLAUDE.md                         # 存在 Claude Agent 时生成
  Plan/
    project.md
    team.json
    agents/
      <agent-id>/
        AGENT.md
        PLAN.md
    collaboration/
      architecture.md
      api-contracts.md
      handoffs.md
    archive/
```

不创建项目版本目录。每个 Agent 只维护 `Plan/agents/<agent-id>/PLAN.md` 这一份活动计划。

## 强制工作流

### 1. 初始化项目

根据实际运行端选择命令：

```bash
python <skill-root>/scripts/vteam.py init --project-root <project-root> --runtime codex
python <skill-root>/scripts/vteam.py init --project-root <project-root> --runtime claude
python <skill-root>/scripts/vteam.py init --project-root <project-root> --runtime codex --runtime claude
```

`codex` 生成 `AGENTS.md`，`claude` 生成 `CLAUDE.md`，混合团队同时生成两个入口。重复初始化只补充运行端和缺失的当前态文档，不覆盖已有项目进度。

### 2. 注册 Agent

让用户明确指定 Agent ID、运行端、角色、职责、至少一个负责模块、永久写入白名单和需要读取的协作文档：

```bash
python <skill-root>/scripts/vteam.py agent \
  --project-root <project-root> \
  --agent-id backend-1 \
  --runtime codex \
  --role backend \
  --responsibility "用户与权限后端" \
  --module backend/auth \
  --allow backend/auth/ \
  --allow tests/auth/ \
  --read-doc Plan/collaboration/api-contracts.md
```

同一角色可以注册多个不同 ID。`Plan/team.json` 是身份、运行端和白名单的机器事实源；重新生成个人约束时以它为准。

### 3. 确认身份并读取最小上下文

严格执行以下顺序：

1. 从用户指令或当前任务上下文确认 `agent-id`；身份不明确时停止并询问用户。
2. 读取项目根 `AGENTS.md` 或 `CLAUDE.md`。
3. 强制读取 `Plan/agents/<agent-id>/AGENT.md`；文件缺失时停止并要求先注册身份。
4. 读取自己的 `PLAN.md` 和 `Plan/project.md`。
5. 只读取个人规则点名且与当前任务直接相关的协作文档。
6. 默认忽略归档、其他 Agent 历史，以及状态为 `completed` 或 `abandoned` 的计划。

### 4. 编写单份计划并等待审批

直接覆盖或修订自己的 `PLAN.md` 当前内容，不为新对话、新需求或普通修复复制新文件。

计划必须记录：

- 当前目标、用户需求、范围、非目标和预计修改路径。
- 验收标准、风险、review 记录和协作依赖。
- 用户批准状态和批准记录。
- 功能任务、测试结果、本地提交哈希和一次性授权记录。
- 当前阻塞、下一步和整体完成结论。

每个任务项只能是可独立验收的完整功能或可独立验证的明确功能修复，并适合形成一次语义完整的本地提交。不要把创建文件、新增方法或改一行配置单独拆成任务，除非它本身就是完整交付。

Review 只审查当前 `PLAN.md` 的需求、范围、模块归属、验收标准、风险和测试计划。记录 `Reviewer`、`Scope`、`Review`、`Blockers`、`Tests` 与 `Required changes`；`Review` 为 `pass`、所有必填项已填写且 `Blockers`、`Required changes` 均为 `none` 或 `无` 后运行：

```bash
python <skill-root>/scripts/vteam.py check-plan --project-root <project-root> --agent-id <agent-id>
```

通过后才可设为 `waiting-approval`。用户批准前禁止实现代码。跨模块、接口、安全或数据迁移任务在提交前增加一次代码 review；审查人只读取当前 diff 与任务测试结果，阻塞项未清零不得提交。

### 5. 实现、测试和本地提交

每个功能任务按以下顺序执行：

1. 实现计划内的完整功能或明确修复。
2. 运行足以证明该功能正确的测试；测试不需要扩展到无关复杂场景。
3. 测试失败时停止提交，记录失败原因，任务保持未完成。
4. 测试通过后暂存当前任务需要提交的文件。
5. 只在本地提交前统一检查一次：

```bash
python <skill-root>/scripts/vteam.py check-scope --project-root <project-root> --agent-id <agent-id>
```

该命令内部只调用一次 `git diff --name-only HEAD`。退出码 `0` 表示范围通过，`2` 表示存在白名单外路径，`1` 表示配置或 Git 错误。

范围通过后使用中文完成本地 Git 提交。禁止自行推送远程，禁止自行合并。本技能不创建、切换、命名或管理 Git 分支。

提交成功后立即在 `PLAN.md` 把任务标记为完成，记录测试命令与结果和本地提交哈希。提交失败时不得填写哈希或标记完成。

## 边界与跨模块协作

白名单表示“无需再次询问即可提交”的默认边界，不限制读取和理解其他模块。Agent 优先处理自己的模块，但允许跨模块修改，前提是能确认调用关系、影响范围和测试方式。

发现白名单外路径时：

1. 暂停当前本地提交。
2. 向用户列出越界路径、修改原因、影响模块和建议提交说明。
3. 询问用户是否允许当前提交。
4. 用户同意后，在当前 `PLAN.md` 记录一次性授权，再提交本次变更。
5. 一次性授权只对当前提交有效，不得修改 `Plan/team.json` 扩大永久白名单。
6. 用户拒绝时，不得提交越界路径；拆分、撤销或交给更合适的 Agent。

简单的一次性跨模块修改只走上述授权流程，不强制创建 handoff。

## 当前态协作文档

只在产物会长期被其他 Agent 消费，或接口、数据结构、模块边界、运行方式、后续集成责任发生变化时维护协作文档：

| 文档 | 当前职责 |
|---|---|
| `Plan/collaboration/architecture.md` | 当前有效模块边界、调用关系、数据流和技术约束 |
| `Plan/collaboration/api-contracts.md` | 当前有效接口、字段、错误约定、示例和集成结果 |
| `Plan/collaboration/handoffs.md` | 仍未完成的跨 Agent 交付物、接收者和验收条件 |

需求澄清、接口变化和进度变化优先覆盖或修订原有段落。不要把协作文档写成聊天记录，也不要为普通新任务重复介绍全部对接历史。对接验证完成或取消后从活动 `handoffs.md` 移除，精简摘要进入归档。

## 安全清理

只对状态为 `completed` 或 `abandoned` 的计划运行：

```bash
python <skill-root>/scripts/vteam.py cleanup --project-root <project-root> --agent-id <agent-id>
```

正常完成计划必须满足：计划 review 已通过；至少一个功能任务；全部任务已完成；每项有测试结果和 7 至 40 位、可由 Git 解析为 commit 的本地提交哈希；相关 handoff 已关闭或转移。废弃计划必须记录非空放弃原因，已完成任务仍保留测试与提交证据。

清理先把计划快照和已关闭对接摘要写入 `Plan/archive/`，再把活动 `PLAN.md` 重置为空白草稿并移除活动 handoff 中的 `completed`、`cancelled` 项。活动计划或当前 Agent 参与的开放 handoff 必须拒绝清理。

## 错误门禁

| 情况 | 必须执行 |
|---|---|
| 无法确认 Agent ID | 停止并询问用户 |
| `team.json` 缺失或无效 | 停止并指出具体字段 |
| 个人 `AGENT.md` 缺失 | 先注册或重新生成身份 |
| review 未通过或有阻塞项 | 修订计划并重新执行 `check-plan` |
| 计划未批准 | 禁止实现代码 |
| 测试失败 | 禁止提交并记录失败原因 |
| 存在越界路径 | 请求当前提交的一次性授权 |
| 本地提交失败 | 不得标记任务完成 |
| 存在开放对接 | 保持 handoff 活动，不推断完成 |
| 计划仍活动 | 禁止清理 |

## 资源

- `scripts/vteam.py`：`init`、`agent`、`check-plan`、`check-scope`、`cleanup` 统一入口。
- `references/root-agents-template.md`：Codex 项目根约束模板。
- `references/root-claude-template.md`：Claude 项目根约束模板。
- `references/personal-agent-template.md`：个人身份、边界和行为模板。
- `references/plan-template.md`：唯一活动计划模板。
- `references/project-template.md`：项目当前态模板。
- `references/architecture-template.md`：架构当前态模板。
- `references/api-contracts-template.md`：接口契约当前态模板。
- `references/handoffs-template.md`：开放对接当前态模板。
- `references/team-template.json`：团队配置初始结构。

所有脚本只依赖 Python 3 标准库和 Git，使用 `pathlib`、参数数组形式的 Git 子进程、UTF-8 文件与 Git 风格相对路径，兼容 Windows 和 macOS。
