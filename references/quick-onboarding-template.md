# 快速入职

当用户以自然语言指定 Agent 身份和业务/项目范围时，将该指令视为默认永久边界授权。

1. 读取项目根规则、`Plan/project.md`、`Plan/team.json`。存在协作需求时运行 `handoff list --project-root <root> --agent-id <自己>`，仅 Read 返回的 `doc` 路径；禁止批量扫描 `Plan/collaboration/active/`。`Plan/collaboration/handoffs.md` 是真源，list 是日常寻址；不限制读取代码或既有可靠资料。
2. 提取用户给出的 Agent ID、角色和范围；当前运行端作为 runtime。用户未给出 Agent ID 时，根据角色自动生成安全的 `<role>-001` 格式 ID，并对照 `Plan/team.json` 递增到首个未占用 ID。
3. 根据目录、架构和现有测试，把语义范围映射为足以完成工作的模块、测试、配置和必要协作文档。
4. 不要为了最小权限而过度拆分目录；“整个 X”“负责 X 项目”“X 端全部代码”应覆盖该范围相关的完整工作面。
5. 将映射结果与 `Plan/team.json` 中已注册 Agent 的业务范围、模块和白名单比较。映射唯一时直接执行 `vteam.py agent` 并输出身份、负责路径、默认可写路径和必读文档。
6. 当前项目没有可区分的物理边界时，允许自行使用 `--module .` 和 `--allow .`。
7. 仅在范围无法映射，或与已注册 Agent 的职责明显争夺同一业务模块时，向用户询问一个最小问题；否则不得因目录粒度反复请求确认。

用户范围变化时，任务仍落在当前授权范围内则直接修订 `PLAN.md`。需要新增长期业务范围时，重新执行 `vteam.py agent --scope <新范围>` 更新该 Agent 的事实与个人规则；仅限当前提交的例外仍走一次性授权。
