# V-Team

V-Team 是面向个人开发者的角色化功能交付技能。它根据任务复杂度和功能范围选择需求、架构、后端、前端、QA 等最小角色链路，避免为普通问题和简单改动制造计划、交接或归档文件。

## 设计目标

- 标准功能先评估价值、需求与技术方案，经用户确认后再编码。
- 角色按“职能 + 功能范围”建立，例如 `backend-sandbox-api`、`frontend-sandbox-console`。
- 后端通过 OpenAPI、Schema、共享类型等真实契约与前端对接。
- 日常过程只存在于对话；仅重大里程碑和跨会话恢复按需留档。
- 不限制改动文件范围，不管理多 Agent 身份、分支、提交、push 或 merge。

## 使用

仅在对话中明确调用：

```text
$v-team 设计并实现沙箱管理功能
```

普通用户无需操作 CLI。技能内部仅在需要契约索引、跨会话恢复或重大里程碑时，使用 `scripts/vteam.py` 维护项目下唯一的 `.vteam/state.json`。

```bash
python scripts/vteam.py --help
python scripts/vteam.py context --project-root /path/to/project \
  --role-id frontend-sandbox-console --capability sandbox-runtime --json
```

技能协议以 [SKILL.md](SKILL.md) 为准；角色链路与留档规则位于 [references](references)。
