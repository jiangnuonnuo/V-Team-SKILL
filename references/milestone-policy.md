# 状态与里程碑

只在契约索引、跨会话恢复或重大里程碑需要落盘时读取。

## 单一状态

`.vteam/state.json` 最多保存 capability 双 Lane 当前事实、contract/Playbook 索引、每个 capability 一条 active，以及重大 milestone 引用。不保存聊天、方案正文、接口正文、测试日志、凭据或历史版本。

跨会话暂停时用 `resume set` 覆盖当前 active，并在相关时记录当前 function。恢复时用 context 只读当前 capability、Lane、角色和相关契约，直接执行记录的下一步；方案未实质变化时不重新分析或确认。完成或放弃时清除 active。新 capability 用 `capability complete` 更新双 Lane 完成事实；旧调用仍可用 `module complete`。普通功能不为了记录完成而首次创建状态。

## 重大里程碑

仅在核心模块首次形成可用闭环、公共协议/核心架构/安全边界重大变化、数据迁移/发布切换/难逆决定，或用户明确要求时记录。

里程碑只保存 id、capability、一句话摘要和持久引用；优先引用 Git commit/tag/release，其次是项目已有架构文档或 ADR。普通修复、普通完成和测试通过不构成里程碑，默认查询不加载里程碑正文。
