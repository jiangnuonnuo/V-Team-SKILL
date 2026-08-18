# Capability 与双 Lane

只在标准或重大产品功能、跨会话功能或需要持久化前后端分工时读取。

一个 capability 是可独立交付的产品结果，不是文件夹或技术组件。先搜索项目代码、现有组件、接口、可用 Skills 和必要官方资料，再判断需求是否 Pass、Reuse、Narrow、Reject、Decision Required 或 Blocked。

通过后分别评估：

- `frontend`：页面、交互、用户状态、权限提示或真实接口消费是否受影响；
- `backend`：业务规则、接口、数据、权限、异步任务或公共契约是否受影响。

每条 Lane 必须为：

- `required`：需要实现；
- `no-change`：无需修改，附项目事实依据；
- `blocked`：暂不能执行，附阻塞原因；
- `active`：正在实现；
- `completed`：实现并有直接验证证据。

产品功能不因一侧无改动而删除该 Lane。纯部署、回答和纯诊断不是产品 capability，不创建虚假的前后端 Lane。

默认顺序是：需求判断 → 方案与架构实施设计 → 后端契约 draft → 前端可选 mock → 后端 ready → 前端真实联调 → 功能/架构/代码质量评审 → 按需发布。没有真实取舍、接口消费或发布时合并或跳过相应动作。

只有跨会话、跨角色契约、Playbook 或重大里程碑需要持久化时，使用 `capability define`、`lane update`、`lane complete` 和 `capability complete`。快速任务只在对话中说明双 Lane 判断，不创建状态。
