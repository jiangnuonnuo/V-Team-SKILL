---
name: v-team
description: Use when a Codex or Claude project needs multi-agent collaboration, distinct roles, module ownership boundaries, temporary Plan-based handoffs, or recoverable active planning across independent agent sessions.
---

# V-Team

## 概述

在一个项目目录内组织 Codex、Claude 或混合 Agent 团队。使用 `Plan/team.json` 保存身份和永久白名单事实，使用项目根约束与个人 `AGENT.md` 强制行为边界，使用单份活动 `PLAN.md` 保持审批、测试、本地提交和恢复进度可追踪。`Plan/` 默认是本地临时协作区，不进入产品 Git 提交；仅用户明确要求后可通过 `plan-git allow-stage` 纳入本地仓库。

核心原则：先确认身份和计划，再实现；默认遵守模块归属，同时允许跨模块；只在本地提交前检查一次暂存范围；临时对接文档只写入 `Plan/`，关闭后删除。

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
      handoffs.md
      active/
        <handoff-id>-<topic>.md
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

`codex` 生成 `AGENTS.md`，`claude` 生成 `CLAUDE.md`，混合团队同时生成两个入口。重复初始化只补充运行端和缺失的活动文档，不覆盖已有项目进度；若项目已是 Git 仓库，会在本地 `.git/info/exclude` 忽略 `/Plan/`，不修改既有 Git 历史。默认 `Plan/` 永不进入产品提交；仅当**用户明确要求**把协作材料纳入**本地**仓库时，才允许运行专用命令 `plan-git allow-stage --i-confirm-user-explicitly-requested`（内部 `git add -f Plan` + 本地授权标记）。Agent 不得自行调用该命令；提交完成后应 `plan-git revoke`。非 Git 根目录不写排除规则。

### 2. 注册 Agent

用户可以直接以自然语言指定 Agent ID、角色和业务/项目范围。Agent 读取当前项目结构后，自行映射足以完成工作的模块、测试、配置与协作文档；映射唯一时直接注册，范围无法映射或与其他 Agent 明显争夺同一业务模块时才询问一个最小问题。初始化项目会生成项目内 `Plan/onboarding.md`，供后续独立会话使用。

注册时使用 Agent ID、运行端、角色、职责、用户范围、至少一个负责模块、永久写入白名单和需要读取的协作文档：

```bash
python <skill-root>/scripts/vteam.py agent \
  --project-root <project-root> \
  --agent-id backend-1 \
  --runtime codex \
  --role backend \
  --responsibility "用户与权限后端" \
  --scope "用户与权限后端全部代码" \
  --module backend/auth \
  --allow backend/auth/ \
  --allow tests/auth/ \
  --read-doc Plan/collaboration/handoffs.md
```

同一角色可以注册多个不同 ID。`Plan/team.json` 保存身份、用户范围、运行端和白名单事实；重新生成个人约束时以它为准。`--scope` 未提供时兼容旧用法并使用 `--responsibility`。

### 3. 确认身份并读取最小上下文

严格执行以下顺序（优先用 `context` 减冷启动 token，**不替代**合同正文与代码的定向 Read）：

1. 从用户指令或当前任务上下文确认 `agent-id`；身份不明确时按 `Plan/onboarding.md` 快速入职，入职完成前禁止实现代码。
2. 运行冷启动索引（推荐，替代「整篇 PLAN + 再单独 list」的固定开场）：

```bash
python <skill-root>/scripts/vteam.py context --project-root <project-root> --agent-id <agent-id>
```

`context` 输出身份、永久白名单、计划 stub（Status/Approval/当前目标/开放任务/阻塞下一步）、`must_read_handoffs` 路径与 skip 指引。需要机器解析时加 `--json`。`context` **不是**计划正文或 handoff 合同的替代品。

3. 若本会话尚未读过且根约束可能影响行为：读取项目根 `AGENTS.md` 或 `CLAUDE.md`。同一会话内文件未变可跳过重读。
4. 强制读取 `Plan/agents/<agent-id>/AGENT.md`（`context` 已标 `exists`）；文件缺失时停止并要求先注册身份。
5. **不要**默认整篇读取 `PLAN.md`。只打开「当前态（会话必读）」：当前目标、范围、验收与风险、Review/批准、**开放**功能任务、阻塞与下一步、协作依赖、一次性授权。默认**不读**「档案（默认不读）」与「已完成任务」表，除非回溯提交/测试证据、填写放弃原因、整体收尾或用户明确要求。需要项目背景时再读 `Plan/project.md`。
6. 对 `context` / 等价 `handoff list` 给出的 `must_read` 且文档存在的路径，**必须** Read 对接正文。禁止批量扫描 `Plan/collaboration/active/`，禁止用 ls/glob 枚举对接正文。将结果写入本 `PLAN.md`「协作依赖」表（会话缓存；真源仍是 `Plan/collaboration/handoffs.md`）。无 must_read 则跳过。
7. 代码、根目录、`doc/` 和 `docs/` 的可靠资料仍可读取。默认忽略其他 Agent 历史，以及状态为 `completed` 或 `abandoned` 的计划。日常寻址以 `context` / `handoff list` 为准。

### 4. 编写单份计划并等待审批

直接覆盖或修订自己的 `PLAN.md` 当前内容，不为新对话、新需求或普通修复复制新文件。计划分两区：

- **当前态（会话必读）**：当前目标、用户需求、范围与非目标、验收与风险、Review/批准、**仅未完成**的功能任务、阻塞与下一步、协作依赖、一次性授权。
- **档案（默认不读）**：已完成任务表（含测试结果与本地提交哈希）、历史需求/范围与 Review 纪要、放弃原因、整体完成结论。

任务完成后把该行从「功能任务」移到「已完成任务」，避免冷启动反复读入已交付证据。`check-plan` / `cleanup` 仍从两表合并解析任务证据。

计划必须记录：

- 当前目标、用户需求、范围、非目标和预计修改路径（当前态）。
- 验收标准、风险、review 记录和协作依赖（当前态）。
- 用户批准状态和批准记录（当前态）。
- 开放功能任务；完成后进档案并保留测试等级、命令与结果、证据有效范围、本地提交哈希（当前态 + 档案）。
- 当前阻塞、下一步；收尾时的整体完成结论与放弃原因（档案侧）。

每个任务项只能是可独立验收的完整功能或可独立验证的明确功能修复，并适合形成一次语义完整的本地提交。功能可用并通过相应验证后即可作为一次 `feat`、`fix` 或任务提交；不要把创建文件、新增方法或改一行配置单独拆成任务，除非它本身就是完整交付。

Review 审查当前 `PLAN.md` 的需求与非目标、模块归属、验收标准、改动范围与风险、测试等级和命令、结果证据以及失败/例外处理。记录 `Reviewer`、`Scope`、`Review`、`Blockers`、`Tests` 与 `Required changes`，并填写测试等级、命令与结果、证据有效范围；`Review` 为 `pass`、所有必填项已填写且 `Blockers`、`Required changes` 均为 `none` 或 `无` 后运行：

```bash
python <skill-root>/scripts/vteam.py check-plan --project-root <project-root> --agent-id <agent-id>
```

通过后才可设为 `waiting-approval`。用户批准前禁止实现代码。Reviewer 默认审阅当前 diff 和已有测试结果，不重复执行测试；仅在证据缺失或过期、结果与验收标准冲突、属于相关完整回归或全仓回归，或发现新的高风险影响时补充验证。跨模块、接口、安全或数据迁移任务在提交前增加一次代码 review，阻塞项未清零不得提交。

### 5. 实现、测试和本地提交

每个功能任务按以下顺序执行：

1. 按风险选择测试等级。定向验证适用于单模块、低风险功能或明确修复；相关完整回归适用于跨模块、公共接口、安全或数据迁移，覆盖受影响模块、直接依赖模块、接口契约/集成测试及必要构建、类型或静态检查；全仓回归只适用于发布、全局基础设施或全局配置变更。一个任务存在多项条件时，以最高适用等级为准。
2. 实现计划内的完整功能或明确修复，并运行该等级足以证明功能正确的测试；定向验证不扩展到无关复杂场景。
3. 同一代码、依赖和运行配置未变化时，成功测试结果可复用为任务完成和提交前验证证据；只有受测代码、相关依赖、配置或测试环境变化后才重新运行对应验证。外部真实接口验证必须限频；失败后先记录和分析原因，不进行无条件自动重试。任何再次真实调用都必须在计划中记录触发条件、次数上限和预期证据；无法判断时询问用户。
4. 测试失败时停止提交，记录失败原因，任务保持未完成。
5. 测试通过后暂存当前完整功能或明确修复需要提交的代码、测试和配置；默认 `Plan/` 中的计划、身份和对接文件均不得暂存。
6. 只在本地提交前统一检查一次：

```bash
python <skill-root>/scripts/vteam.py check-scope --project-root <project-root> --agent-id <agent-id>
```

该命令内部只调用一次 `git diff --cached --name-only`，只检查准备提交的内容。退出码 `0` 表示范围通过，`2` 表示存在越界路径或未授权的 `Plan/` 路径，`1` 表示配置或 Git 错误。

范围通过后使用中文完成该完整功能或明确修复的一次本地 Git 提交；提交按可用功能或修复划分，而不是按文件集合或文件类型划分。默认 `Plan/` 不能通过白名单外「一次性授权」绕过。仅当用户**明确要求**上传/纳入本地仓库时，使用：

```bash
python <skill-root>/scripts/vteam.py plan-git allow-stage \
  --project-root <project-root> \
  --i-confirm-user-explicitly-requested
python <skill-root>/scripts/vteam.py check-scope --project-root <project-root> --agent-id <agent-id>
# 本地 commit 成功后
python <skill-root>/scripts/vteam.py plan-git revoke --project-root <project-root>
```

`plan-git status` 可查看排除与授权状态。禁止自行推送远程，禁止自行合并。本技能不创建、切换、命名或管理 Git 分支。

提交成功后立即在 `PLAN.md` 把任务标记为完成，记录测试命令与结果和本地提交哈希。提交失败时不得填写哈希或标记完成。

## 边界与跨模块协作

白名单表示“无需再次询问即可提交”的默认边界，不限制读取和理解其他模块。Agent 优先处理自己的模块，但允许跨模块修改，前提是能确认调用关系、影响范围和测试方式。

发现非 `Plan/` 的白名单外路径时：

1. 暂停当前本地提交。
2. 向用户列出越界路径、修改原因、影响模块和建议提交说明。
3. 询问用户是否允许当前提交。
4. 用户同意后，在当前 `PLAN.md` 记录一次性授权，再提交本次变更。
5. 一次性授权只对当前提交有效，不得修改 `Plan/team.json` 扩大永久白名单。
6. 用户拒绝时，不得提交越界路径；拆分、撤销或交给更合适的 Agent。

简单的一次性跨模块修改只走上述授权流程，不强制创建 handoff。

## 如何拆分 Agent（角色默认，切片可选）

**默认仍按角色/模块注册**（如 `backend-1`、`frontend-1`）：永久白名单对准技术边界，职责清晰，适合并行和书面对接。不要为了「少建 Agent」而取消角色编制。

个人全栈或一人编排多个会话时，**交付单元（一条用户功能）** 常跨多层，与 **所有权单元（角色目录）** 不是同一刀。按下表选择，避免每个小改动都外交，也避免假分离：

| 场景 | 怎么拆 | 对接 |
|------|--------|------|
| 前后端/多角色要**并行**，接口会变、需要稳定契约 | **按角色**注册；白名单各管一层 | 接收方必须消费契约时用 `handoff create`；接收会话启动先 `handoff list` |
| 功能是**一条垂直链路**，且同一时期 mainly **一个会话**做完（如小登录全栈） | 可注册**切片 Agent**（或给角色 Agent 配置**多前缀** `--allow`，覆盖该链路相关目录与测试） | 无第二消费方则**不建** handoff；说明写在自己的 `PLAN.md` |
| 已有角色 Agent，只**偶发**改对面一层 | 保持原身份 | **一次性授权**，不扩 `team.json`，不强制 handoff |
| 两角色已并行，中途发现边界画错 | 用户确认后调整 `--allow` / 增补模块，或把剩余工作交给更合适的 `agent-id` | 已有 open handoff 则修订正文，不复制 topic |

约束（三条不变）：

1. **身份仍要唯一 `agent-id`**；切片也是正式注册，不是匿名「什么都改」。
2. **白名单仍是提交边界**；切片只是把边界画成「本功能相关的多棵目录」，不是关闭 `check-scope`。
3. **有另一已注册 Agent 必须靠契约才能交付时，必须 handoff**；仅为自己备忘不建对接。

注册切片示例（路径按项目替换）：

```bash
python <skill-root>/scripts/vteam.py agent \
  --project-root <project-root> \
  --agent-id auth-slice \
  --runtime claude \
  --role fullstack \
  --responsibility "登录注册垂直切片" \
  --scope "登录相关前后端与测试" \
  --module backend/auth \
  --module web/login \
  --allow backend/auth/ \
  --allow web/login/ \
  --allow tests/auth/ \
  --read-doc Plan/collaboration/handoffs.md
```

一人操作多个 Agent 时：同时尽量只让一个身份处于「可本地提交」；冲突与集成以手中的 handoff 契约和用户裁决为准。本技能仍不管理 Git 分支。

## 临时协作文档

默认不建对接。只有另一已注册 Agent 必须消费本契约/接口才能完成用户可感知交付时，才建立临时对接：

```bash
python <skill-root>/scripts/vteam.py handoff create \
  --project-root <project-root> \
  --from <proposer-id> --to <receiver-id> \
  --topic <slug> --deliverable "..." --acceptance "..."
```

| 文档 / 命令 | 当前职责 |
|---|---|
| `handoff list` | 接收/提出方精确列出应读路径；启动协作时必用 |
| `handoff create` | 一键登记 + 生成 `active/<id>-<topic>.md`；禁止手搓未登记文件 |
| `handoff doctor` | 报告孤儿 active、缺失路径、无效 agent-id；不默认删除 |
| `Plan/collaboration/handoffs.md` | 对接真源表；优先索引 |
| `Plan/collaboration/active/<handoff-id>-<topic>.md` | 临时正文；须经 create 或表登记后才由接收者使用 |

仅自用说明写在自己的 `PLAN.md`。简单跨模块走一次性授权，不建 handoff。同 from+to+topic 已有 open/in-progress 时修订旧文档，不新建。验收后把状态改为 `completed` 或 `cancelled`（可直接改表）；功能完成后禁止再写归档、对接总结或多余对接文档。`cleanup` 再物理删除文档和关闭条目，不归档临时材料。open handoff 不阻止实现；`check-plan` 不因 handoff 失败。新建对接不得写入项目根目录、`doc/` 或 `docs/`。

## 安全清理

只对状态为 `completed` 或 `abandoned` 的计划运行：

```bash
python <skill-root>/scripts/vteam.py cleanup --project-root <project-root> --agent-id <agent-id>
```

正常完成计划必须满足：计划 review 已通过；至少一个功能任务；全部任务已完成；每项有测试结果和 7 至 40 位、可由 Git 解析为 commit 的本地提交哈希；相关 handoff 已关闭或转移。废弃计划必须记录非空放弃原因，已完成任务仍保留测试与提交证据。

清理把活动 `PLAN.md` 重置为空白草稿，删除已关闭 handoff 登记的 `Plan/collaboration/active/` 临时文档，并移除 `completed`、`cancelled` 条目；不归档这些材料。活动计划或当前 Agent 参与的开放 handoff 必须拒绝清理。

## 错误门禁

| 情况 | 必须执行 |
|---|---|
| 无法确认 Agent ID | 停止并询问用户 |
| `team.json` 缺失或无效 | 停止并指出具体字段 |
| 个人 `AGENT.md` 缺失 | 先注册或重新生成身份 |
| review 未通过或有阻塞项 | 修订计划并重新执行 `check-plan` |
| 计划未批准 | 禁止实现代码 |
| 测试失败 | 禁止提交并记录失败原因 |
| 暂存 `Plan/` 路径（无用户明确授权） | 从暂存区移除；不得用白名单外一次性授权提交；仅用户明确要求后走 `plan-git allow-stage` |
| 存在越界路径 | 请求当前提交的一次性授权 |
| 本地提交失败 | 不得标记任务完成 |
| 存在开放对接 | 保持 handoff 活动，不推断完成 |
| 计划仍活动 | 禁止清理 |

## 资源

- `scripts/vteam.py`：`init`、`agent`、`context`、`check-plan`、`check-scope`、`cleanup`、`plan-git status|allow-stage|revoke`、`handoff list|show|create|doctor` 统一入口。
- `references/root-agents-template.md`：Codex 项目根约束模板。
- `references/root-claude-template.md`：Claude 项目根约束模板。
- `references/personal-agent-template.md`：个人身份、边界和行为模板。
- `references/quick-onboarding-template.md`：从用户身份和业务范围生成个人约束的提示模板。
- `references/plan-template.md`：唯一活动计划模板（当前态 / 档案分区 + 协作依赖缓存表）。
- `references/project-template.md`：项目当前态模板。
- `references/handoffs-template.md`：开放对接当前态模板。
- `references/team-template.json`：团队配置初始结构。

所有脚本只依赖 Python 3 标准库和 Git，使用 `pathlib`、参数数组形式的 Git 子进程、UTF-8 文件与 Git 风格相对路径，兼容 Windows 和 macOS。
