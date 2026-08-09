---
name: v-team
description: 个人功能开发的角色化交付技能。仅在用户明确调用 `$v-team` 时使用；根据任务复杂度选择需求、架构、后端、前端、QA 等最小角色链路，先评估价值与方案，再在用户确认后开发，并通过可发现的接口契约完成前后端对接。普通问答、简单重复改动和未明确调用时不要使用。
---

# V-Team

V-Team 是个人使用的功能交付工作流，不是多 Agent 编排器。它按“功能 + 职能”临时确定角色，例如 `backend-sandbox-api`、`frontend-sandbox-console`、`architect-agent-runtime`。一个角色对一个功能结果负责；角色可以由同一 Agent 依次承担，也可以由不同 Agent 承担。

## 核心原则

1. 用户没有明确调用 `$v-team` 时，不触发本技能。
2. 先判断任务路线，再决定是否分析、设计或编码。
3. 标准功能先完成价值、需求与技术方案沟通；用户确认前不修改业务代码。
4. 不为问题、分析、方案草稿、日常测试或普通状态新建文件。
5. 实际交付物优先写入产品代码、测试、OpenAPI、Schema、共享类型和现有架构文档。
6. 只读取当前角色、当前能力和当前契约所需的最小上下文。
7. 不强制路径白名单、模块所有权、独立 AGENT/PLAN、handoff 文档、提交或分支治理。

## 第一步：选择任务路线

读取 [role-router.md](references/role-router.md)，把任务分为以下一种路线：

- **问答/分析**：只回答和分析；不改代码，不创建 `.vteam`，不留档。
- **快速改动**：需求明确、重复性强、低风险且不改变公共契约、数据、安全或架构；直接实现并做最小充分验证，不创建 V-Team 状态。
- **标准功能**：有新用户能力或行为变化；走价值/需求 → 技术方案/架构 → 用户确认 → 角色开发 → 验证闭环。
- **重大改造**：跨模块、难回滚、公共协议/数据迁移/安全边界/核心架构变化，或需要跨会话恢复；在标准功能路线之上使用紧凑状态和里程碑。

无法确定时按风险更高的一档处理。只要涉及公共 API、Schema、数据迁移、权限、安全、兼容性或架构边界，就不能走快速改动。

## 第二步：建立功能身份

为本次功能使用稳定的 `capability_id`，推荐小写短横线，例如 `sandbox-runtime`。按实际结果选择最少角色，并用 `<职能>-<功能范围>` 命名角色：

- `requirement-*`：需求、价值、范围与验收
- `architect-*`：边界、技术选型与落地架构
- `backend-*`：业务规则、接口、数据与服务实现
- `frontend-*`：用户流程、UI、页面、接口集成与浏览器验证
- `qa-*`：风险、端到端验收与缺陷复测

不要因为存在角色就全部启用。纯后端能力不必启用前端；纯 UI 改动不必启用架构师；高风险全栈功能通常需要完整链路。

## 第三步：执行角色链路

根据选中的角色只读取对应参考：

- 需求：[role-requirement.md](references/role-requirement.md)
- 架构：[role-architect.md](references/role-architect.md)
- 后端：[role-backend.md](references/role-backend.md)
- 前端：[role-frontend.md](references/role-frontend.md)
- QA：[role-qa.md](references/role-qa.md)

角色链路不是一份通用 PLAN：

- 需求角色先回答“为什么做、做什么、不做什么、怎样算完成”。
- 架构角色把确认后的需求转成可落地边界、组件、数据流、契约、迁移与回滚方案。
- 后端角色先发布可消费的契约，再实现并验证服务。
- 前端角色先完成用户流与 UI 状态设计，可基于 draft 契约做 mock；契约 ready 后再真实联调。
- QA 角色围绕验收标准和风险做模块与跨角色闭环。

## 标准功能的沟通门禁

在修改业务代码前，在对话中给用户一份紧凑结论，至少包含：

1. 用户问题、价值与使用频率；现有能力能否复用；不开发是否更合理。
2. 目标、范围、非目标、关键场景和可验证验收条件。
3. 可行性、约束、风险及至少一个替代方案。
4. 推荐技术方案：边界、关键组件、数据流、契约、兼容/迁移/回滚。
5. 建议启用的角色链路和实现顺序。

明确请求用户确认该方案。确认前可以只读检查代码、验证可行性或做非业务性的探索，不得开始功能实现。若用户已在同一上下文中明确批准了完整方案，无需重复确认。

快速改动不走此门禁；重大改造不得跳过。

## 前后端契约对接

涉及跨角色接口时读取 [contract-policy.md](references/contract-policy.md)。核心约定：

1. 后端把真实契约保存在产品仓库既有来源中，如 OpenAPI、GraphQL Schema、protobuf、JSON Schema、共享类型或契约测试。
2. V-Team 只保存契约索引，不复制接口正文。
3. 契约索引必须包含稳定 `id`、`capability`、`provider`、`consumers`、`source`、`source_ref`、`status`、`version`、`breaking`，以及可选 `mock`、`verification`。
4. 前端按 `capability + consumer role` 发现契约：零个则阻塞并报告；一个则直接使用；多个则列出供选择，禁止猜测。
5. `draft` 只允许 UI/mock 开发；`ready` 或 `verified` 才允许真实集成；`blocked` 明确阻塞；`deprecated` 默认不参与发现。

如果项目已有 API Catalog 或 Schema Registry，优先使用它。否则按需调用 `scripts/vteam.py`，仅维护一个 `.vteam/state.json`。

## 状态与留档

默认不创建状态文件。仅在以下有意义事件发生时写入：

- 后端发布或更新跨角色契约索引；
- 功能需要跨会话恢复，写入一条当前恢复状态；
- 模块完成，更新该能力的当前完成事实并清除恢复状态；
- 用户明确要求，或满足重大里程碑条件。

状态规则见 [milestone-policy.md](references/milestone-policy.md)：

- 每个 capability 最多一条 `active`，更新时覆盖，不追加过程日志。
- 完成或放弃后删除 `active`。
- 普通模块完成不生成总结文档或 ADR。
- 重大里程碑优先引用 Git commit/tag/release、现有架构文档或 ADR。
- 不读取与当前 capability 无关的历史正文。

脚本仅供 Agent 执行确定性操作，用户不需要记命令：

```bash
python scripts/vteam.py context --project-root <root> --role-id frontend-sandbox-console --capability sandbox-runtime --json
python scripts/vteam.py contract discover --project-root <root> --capability sandbox-runtime --consumer frontend-sandbox-console --json
```

需要写状态时再执行 `contract publish|verify|deprecate`、`resume set|clear`、`module complete` 或 `milestone record`。先运行 `--help` 获取字段，不把 CLI 当作用户流程。

## 实现与验证

用户批准标准/重大方案后：

1. 读取当前角色参考、相关代码和已发现契约。
2. 实现当前角色负责的完整功能结果，不按文件机械拆角色。
3. 按风险执行必要的单元、契约、集成、浏览器或端到端测试。
4. 检查加载、空、错误、权限、网络、重复提交、兼容和回滚等相关边界。
5. 结果未达到验收条件时继续修复，不用文档更新代替可运行结果。
6. 完成后向用户报告实际变更、验证结果、风险和仍需对接项。

V-Team 不自行要求本地提交、push、merge 或 PR；是否执行 Git 操作以用户请求和项目规则为准。

## 完成定义

一个模块只有同时满足以下条件才算完成：

- 用户可见或调用方可用的闭环已经实现；
- 相关验收条件通过；
- 跨角色契约已达到 `ready` 或 `verified`，消费者能定位真实来源；
- 必要测试通过，失败和未覆盖项已明确；
- 临时恢复状态已清除；
- 没有为了“交付”额外制造无用途文档。
