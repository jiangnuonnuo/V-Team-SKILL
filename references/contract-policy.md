# 跨角色契约

仅在提供者与消费者需要对接时读取。

## 权威来源与索引

接口正文必须留在产品仓库或既有平台的 OpenAPI、GraphQL Schema、protobuf、JSON Schema、共享类型或契约测试中。已有 Catalog/Registry 时复用；否则 `.vteam/state.json` 只保存定位索引，不复制字段和示例。本地 `source_ref` 必须指向实际文件；外部平台使用明确 URI。

索引字段：`id`、`capability`、`provider`、`consumers`、`source`、`source_ref`、`status`、`version`、`breaking`，以及可选的 `mock`、`verification`。公共全栈 capability 通常由 backend Lane 提供、frontend Lane 消费。

## 状态

- `draft`：结构可能变化，只允许设计和 mock。
- `ready`：提供者实现完成并附一条直接验证证据，可以真实集成。
- `verified`：消费者或契约测试已验证。
- `blocked`：不能集成，必须说明原因。
- `deprecated`：停止新消费，默认不参与发现。

## 发现与生命周期

消费者冷启动先按完整角色 ID 查询 context；不知道 capability 时把返回的相关契约当作待对接入口。之后按 `capability + 角色 ID` 过滤并排除 deprecated：一个匹配直接使用；零个明确阻塞；多个要求指定 contract id。禁止按相似名称或修改时间猜测。

- `publish`：创建或更新索引；同一 id 不改变 capability/provider，ready 必须附提供者证据。
- `discover`：只读，不创建状态。
- `verify`：只允许登记的 consumer 记录一次真实联调证据。
- `deprecate`：记录原因和可选替代项。
