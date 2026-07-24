# V-Team 说明

这是一份偏「为什么 + 怎么串起来」的说明，给已经安装 skill、或想快速看清结构的人。  
可执行规则以仓库根目录 [`SKILL.md`](../SKILL.md) 为准。

## 它是什么

V-Team 是 Codex / Claude 的多 Agent **项目协作技能**，不是 CI 平台，也不是远程编排器。

它在单个项目目录里生成：

- 根约束（`AGENTS.md` / `CLAUDE.md`）
- 个人身份（`Plan/agents/<id>/AGENT.md`）
- 唯一活动计划（`PLAN.md`）
- 本地协作区（`Plan/`，默认不进 Git）
- 可执行门禁（`check-plan` / `check-scope` / `cleanup` / `handoff`）

目标很具体：**让多个 Agent 在同一仓库里并行，但有身份、有边界、有审批、有证据、有清理。**

## 它解决什么

| 问题 | V-Team 的做法 |
|------|----------------|
| 多个会话互相踩 | 每个 Agent 有 ID、角色、白名单 |
| 没想清楚就改代码 | 计划未批准，禁止实现 |
| 改完不知能否提交 | 风险测试 + `check-scope` |
| 协作材料污染历史 | 进本地 `Plan/`，完成即清理 |
| Codex / Claude 混用 | 同一套流程，双入口文件 |
| Agent 代管 Git | **不做** push / merge / 分支管理 |

## 系统结构

![V-Team System Architecture](../assets/archify/v-team-system.png)

交互版：[v-team-system.html](../assets/archify/v-team-system.html)

主路径：

```text
You / Team Lead
  → Agent Hosts (Codex · Claude · mixed)
  → Root Constraints (AGENTS.md / CLAUDE.md)
  → AGENT.md
  → PLAN.md
  → Quality Gates (check-plan · check-scope · handoff · cleanup)
  → Local Git (feat / fix · no push)
```

事实源：

| 组件 | 作用 |
|------|------|
| `scripts/vteam.py` | CLI：init / agent / gates / handoff |
| `references/*` | 模板 |
| `Plan/team.json` | 身份与永久白名单 |
| `Plan/agents/<id>/AGENT.md` | 个人边界 |
| `Plan/agents/<id>/PLAN.md` | 唯一活动计划 |
| `Plan/collaboration/*` | 临时对接，完成即删 |

产品代码进 Git；协作记忆留在本地 `Plan/`。

## 强制工作流

![V-Team Forced Delivery Loop](../assets/archify/v-team-workflow.png)

交互版：[v-team-workflow.html](../assets/archify/v-team-workflow.html)

1. 确认 ID  
2. 读规则（根约束 + AGENT.md）  
3. `handoff list`（仅读返回路径，禁止扫 `active/`）  
4. 写唯一活动计划（协作依赖表缓存 list）  
5. 独立 review  
6. `check-plan`  
7. 用户批准  
8. 实现（完整功能 / 明确修复）  
9. 风险分级测试  
10. `check-scope`  
11. 本地提交  
12. 需要时 `handoff create`；完成后关状态并 `cleanup`  

硬停止：

- 身份缺失 → 禁止开工  
- 计划未批准 → 禁止实现  
- 测试失败 → 禁止提交  
- staged 含 `Plan/` → 拒绝  
- 越界路径 → 一次性授权，不永久改白名单  

## 几个关键约定

### 任务粒度

任务项是「可独立验收的完整功能」或「可独立验证的明确修复」，再对应一次语义提交。  
不为“新建一个文件 / 加一个方法 / 改一行配置”单独拆任务（除非那本身就是完整交付）。

### 测试深度

| 等级 | 场景 |
|------|------|
| 定向验证 | 单模块、低风险 |
| 相关回归 | 跨模块、公共接口、安全、迁移 |
| 全仓回归 | 发布、全局基础设施、全局配置 |

证据可复用，直到代码 / 依赖 / 配置真正变化。

### 白名单

白名单是「默认可不问即可提交的范围」，不是禁止阅读，也不是禁止跨模块。  
跨模块时：

- 一次性修改 → 用户当前提交授权  
- 需要后续 Agent 集成 → 写临时 handoff  
- 授权不自动扩永久白名单  

### 协作文档

默认不建对接。仅当另一 Agent 必须后续集成时：

- 用 `handoff create` 登记并生成 `Plan/collaboration/active/<id>-<topic>.md`
- 接收方用 `handoff list` 精确读取；禁止扫 `active/`
- 真源表：`Plan/collaboration/handoffs.md`
- 完成或取消后 `cleanup` 物理删除，不归档
- `handoff doctor` 可查孤儿文档；open handoff 不阻止实现

## 生成结果

```text
<project-root>/
  AGENTS.md and/or CLAUDE.md
  Plan/
    project.md
    onboarding.md
    team.json
    agents/<agent-id>/AGENT.md
    agents/<agent-id>/PLAN.md
    collaboration/handoffs.md
    collaboration/active/...
```

CLI：

```bash
python scripts/vteam.py init
python scripts/vteam.py agent
python scripts/vteam.py handoff list|create|doctor
python scripts/vteam.py check-plan
python scripts/vteam.py check-scope
python scripts/vteam.py cleanup
```

## 设计边界

- 不管分支
- 不 push
- 不 merge / 不开 PR
- 不装 hook
- 不在每次写文件前做路径检查
- 不保存完整聊天日志

## 资源

| 路径 | 作用 |
|------|------|
| [`SKILL.md`](../SKILL.md) | 完整协议 |
| [`README.md`](../README.md) | 仓库首页与快速使用 |
| [`scripts/vteam.py`](../scripts/vteam.py) | CLI |
| [`references/`](../references/) | 模板 |
| [`tests/test_vteam.py`](../tests/test_vteam.py) | 测试 |
| [`assets/archify/v-team-system.png`](../assets/archify/v-team-system.png) | 架构图 |
| [`assets/archify/v-team-workflow.png`](../assets/archify/v-team-workflow.png) | 工作流图 |
| [`assets/archify/*.html`](../assets/archify/) | 交互图 |
| [`assets/archify/*-card.png`](../assets/archify/) | 1200×630 预览卡 |

完整强制规则与异常门禁以 [`SKILL.md`](../SKILL.md) 为准。
