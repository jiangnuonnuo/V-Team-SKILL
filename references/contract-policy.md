# 契约发现策略

## 权威来源

契约正文必须存在于产品仓库或现有契约平台：

- OpenAPI；
- GraphQL Schema；
- protobuf；
- JSON Schema；
- 前后端共享类型；
- 可执行契约测试。

项目已有 API Catalog 或 Schema Registry 时直接复用。`.vteam/state.json` 只是缺少现有索引时的轻量 fallback，不保存接口正文。

## 索引字段

每个契约包含：

| 字段 | 含义 |
|---|---|
| `id` | 稳定契约标识 |
| `capability` | 所属功能能力 |
| `provider` | 提供者角色 ID |
| `consumers` | 消费者角色 ID 列表 |
| `source` | openapi/graphql/protobuf/json-schema/shared-types/contract-test |
| `source_ref` | 仓库相对路径、操作 ID 或平台定位符 |
| `status` | draft/ready/verified/blocked/deprecated |
| `version` | 契约版本 |
| `breaking` | 是否为破坏性变化 |
| `mock` | 可选 mock/fixture 定位符 |
| `verification` | 可选验证记录 |

索引不复制请求、响应、字段说明或长篇示例。

## 状态语义

- `draft`：结构仍可能变化；只允许设计、类型预研和 mock 开发。
- `ready`：提供者已实现并验证，消费者可以真实集成。
- `verified`：至少一个消费者或契约测试已验证真实兼容。
- `blocked`：已知不能集成，必须说明阻塞。
- `deprecated`：停止新消费，默认不参与发现。

## 发现算法

1. 按 `capability` 和完整 consumer role ID 过滤。
2. 排除 `deprecated`。
3. 零个：明确返回未发现，真实集成停止。
4. 一个：返回该契约及是否允许真实集成。
5. 多个：返回候选并要求用 contract id 明确选择。

不得按相似名字、最新修改时间或主观判断静默选择。

## 生命周期动作

- `contract publish`：后端创建或更新索引；同一 id 不得改变 capability/provider 身份。
- `contract discover`：只读发现，不创建状态。
- `contract verify`：写入验证者和证据，状态改为 verified。
- `contract deprecate`：写入原因和可选替代契约，停止新消费。
