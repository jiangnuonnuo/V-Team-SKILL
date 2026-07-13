# Agent `{{AGENT_ID}}` 个人约束

## 身份与职责

- Agent ID: `{{AGENT_ID}}`
- Runtime: `{{RUNTIME}}`
- Role: `{{ROLE}}`
- Responsibility: {{RESPONSIBILITY}}
- 用户授权范围：{{SCOPE_STATEMENT}}

主要负责模块：

{{MODULES}}

## 提交白名单

以下路径允许在完成测试后直接进入本地提交流程：

{{WRITE_WHITELIST}}

白名单只限制未经用户确认可以直接提交的路径，不禁止读取其他模块，也不禁止理解跨模块调用关系。如果跨模块修改更直接，并且你能确认影响和测试方式，可以完成修改；本地提交前发现白名单外路径时，必须列出路径、原因和影响并询问用户。用户批准只构成当前提交的一次性授权，必须记录在本文件对应的 `PLAN.md`，不得写回 `Plan/team.json` 扩大永久白名单。

## 强制读取顺序

1. 项目根目录 `AGENTS.md` 或 `CLAUDE.md`。
2. 本文件 `Plan/agents/{{AGENT_ID}}/AGENT.md`。
3. 唯一活动计划 `Plan/agents/{{AGENT_ID}}/PLAN.md`。
4. `Plan/project.md`。
5. 下列与当前任务直接相关的当前态协作文档：

{{COLLABORATION_DOCS}}

默认忽略 `Plan/archive/`、状态为 `completed` 或 `abandoned` 的计划，以及与当前任务无关的其他 Agent 历史。

## 计划、测试与提交

1. 直接维护唯一活动 `PLAN.md`，新需求覆盖或修订当前事实，不复制 `final-2`、`review-new` 或每轮对话文件。
2. 每个任务项只能是可独立验收的完整功能或可独立验证的明确功能修复，并适合形成一次语义完整的本地提交。
3. 先完成需求分析、验收标准、风险和一次计划 review；记录 Reviewer、Scope、Review、Blockers、Tests 与 Required changes，运行 `check-plan` 通过后才可设为 `waiting-approval`；用户批准前禁止实现代码。
4. 每次只执行一个未完成任务项，完成后运行足以证明该功能正确的测试，不扩展无关测试范围。
5. 测试失败时禁止提交并记录失败原因。
6. 测试通过后暂存本任务文件，只统一执行一次 `git diff --name-only HEAD` 并与 `Plan/team.json` 白名单核对。
7. 范围处理完成后使用中文提交到本地 Git；禁止自行推送远程或合并代码，本规则不管理分支。
8. 提交成功后更新任务状态、测试结果和本地提交哈希；提交失败时不得标记完成。
9. 跨模块、接口、安全或数据迁移任务在提交前增加一次代码 review；审查人只读取当前 diff 与任务测试结果，阻塞项未清零不得提交。

## 协作责任

1. 优先在负责模块内工作，但不要把边界理解为禁止跨模块修改。
2. 只有长期被其他 Agent 消费的接口、数据结构、模块边界或未闭环依赖才需要更新协作文档。
3. 架构变化维护 `Plan/collaboration/architecture.md`；接口变化由生产方维护 `Plan/collaboration/api-contracts.md`；未完成对接维护 `Plan/collaboration/handoffs.md`。
4. 简单的一次性跨模块修改只走提交前一次性授权，不强制创建 handoff。
5. 对接验证完成后从活动 handoff 移除；完成或废弃计划满足证据条件后运行安全清理。
