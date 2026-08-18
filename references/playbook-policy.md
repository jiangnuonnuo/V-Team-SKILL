# Playbook 沉淀

只在重复的开发、测试、构建、部署、健康检查或回滚步骤已经有真实项目来源和验证证据时读取。

Playbook 是可发现的操作索引，不是新的执行器。正文继续留在项目的 package scripts、Makefile、CI、部署脚本或 Runbook 中；索引只保存 function、role、action、来源、前置条件、成功检查、可选回滚来源和验证证据。

发布条件：

1. `source_ref` 指向项目内真实文件或明确外部 Registry；
2. 至少有一条成功检查；
3. 标记为 `verified` 时必须附直接验证证据；
4. operations Playbook 必须附回滚来源；
5. 不保存密码、Token、私钥、完整日志或临时输出。

发现时只使用 `verified` Playbook：一个匹配直接使用，多个明确选择，零个继续读取项目事实或报告缺口。过期操作用 `deprecate` 停用，不让旧命令继续在项目里像幽灵一样加班。
