# 当前跨 Agent 对接

| ID | 提出者 | 接收者 | 对接文档 | 交付物 | 验收条件 | 状态 |
|---|---|---|---|---|---|---|

## 维护规则

- 默认不建对接。推荐用 `handoff create` 登记并生成 `Plan/collaboration/active/<id>-<topic>.md`；手写须保持 7 列且路径合法。
- 接收方用 `handoff list` 精确读取，禁止批量扫描 `active/`。
- 没有单独文档时“对接文档”填写 `-`；有文档时只能是 `Plan/collaboration/active/` 下路径。
- 状态使用 `open`、`in-progress`、`completed` 或 `cancelled`。
- 对接完成并验证后标记为 `completed` 或 `cancelled`；运行 `cleanup` 时删除文档并从活动表移除，不归档临时对接材料。
- `handoff doctor` 检查孤儿文件与无效 agent-id；不默认删除。
- 简单的一次性跨模块修改不强制登记。
