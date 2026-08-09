# 状态与里程碑

只在契约索引、跨会话恢复或重大里程碑需要落盘时读取。

## 单一状态

`.vteam/state.json` 最多保存 capability 当前事实、contract 索引、每个 capability 一条 active，以及重大 milestone 引用。不保存聊天、方案正文、接口正文、测试日志或历史版本。

跨会话暂停时用 `resume set` 覆盖当前 active；恢复上下文只读当前 capability；完成或放弃时清除。若状态已经存在，模块闭环后用 `module complete` 更新当前事实并清除 active。普通功能不为了记录完成而首次创建状态。

## 重大里程碑

仅在核心模块首次形成可用闭环、公共协议/核心架构/安全边界重大变化、数据迁移/发布切换/难逆决定，或用户明确要求时记录。

里程碑只保存 id、capability、一句话摘要和持久引用；优先引用 Git commit/tag/release，其次是项目已有架构文档或 ADR。普通修复、普通完成和测试通过不构成里程碑，默认查询不加载里程碑正文。
