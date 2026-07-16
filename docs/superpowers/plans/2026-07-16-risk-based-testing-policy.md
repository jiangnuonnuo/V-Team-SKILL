# V-Team 风险分级测试策略 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 V-Team 的测试和 Review 规则改为风险分级、可复用验证证据的流程，避免对未变化代码重复测试。

**Architecture:** 保留 `vteam.py` 的审批、范围检查和归档门禁，仅调整 `SKILL.md` 与生成的 Agent/计划模板。通过 `tests/test_vteam.py` 的文本契约测试锁定三档测试策略、证据复用和 Review 不默认重跑测试的行为。

**Tech Stack:** Markdown、Python 3 标准库 `unittest`、Git。

## Global Constraints

- 不修改 `scripts/vteam.py` 的审批、范围检查和归档流程。
- 定向验证、相关完整回归和全仓回归必须有清晰、互斥的触发条件。
- 外部真实接口验证必须限频，失败后不得无条件自动重试；再次调用前必须记录触发条件、次数上限和预期证据。
- 同一代码、依赖和运行配置未变化时，成功测试证据可复用。
- Review 审查需求、验收、风险和证据；除缺失/过期证据或高风险变更外，不默认重跑测试。

---

### Task 1: 为风险分级策略建立失败的契约测试

**Files:**
- Modify: `tests/test_vteam.py:822-968`

**Interfaces:**
- Consumes: `SKILL.md` 与 `references/` 中的技能和模板文本。
- Produces: `SkillContractTests` 中验证风险分级测试、证据复用、Review 边界和计划字段的测试方法。

- [ ] **Step 1: 添加失败测试**

在 `SkillContractTests` 中加入以下测试；它们在规则尚未更新时必须失败：

```python
    def test_skill_documents_risk_based_testing_and_evidence_reuse(self) -> None:
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        for fragment in [
            "定向验证",
            "相关完整回归",
            "全仓回归",
            "同一代码、依赖和运行配置未变化",
            "不进行无条件自动重试",
            "Reviewer 默认审阅当前 diff 和已有测试结果，不重复执行测试",
        ]:
            self.assertIn(fragment, content)

    def test_generated_agent_rules_use_risk_based_testing_and_result_review(self) -> None:
        for relative_path in [
            "references/root-agents-template.md",
            "references/root-claude-template.md",
            "references/personal-agent-template.md",
        ]:
            content = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("按风险选择最小有效验证", content)
            self.assertIn("同一代码、依赖和运行配置未变化", content)
            self.assertIn("需求、验收标准、改动范围与风险", content)

    def test_plan_template_records_test_level_and_evidence_validity(self) -> None:
        content = (REPOSITORY_ROOT / "references" / "plan-template.md").read_text(
            encoding="utf-8"
        )

        for fragment in [
            "- Test level: `pending`",
            "- Test commands and results: `-`",
            "- Evidence validity: `-`",
        ]:
            self.assertIn(fragment, content)
```

- [ ] **Step 2: 运行失败测试**

Run: `python3 -m unittest tests.test_vteam.SkillContractTests -v`

Expected: FAIL，缺少上述风险分级策略、证据复用或计划字段文本。

### Task 2: 统一技能与生成模板的测试、Review 规则

**Files:**
- Modify: `SKILL.md:89-125`
- Modify: `references/root-agents-template.md:10-18`
- Modify: `references/root-claude-template.md:10-18`
- Modify: `references/personal-agent-template.md:35-45`
- Modify: `references/plan-template.md:26-35`

**Interfaces:**
- Consumes: Task 1 的文本契约与已批准设计文档。
- Produces: 一致的测试等级定义、证据复用条件、外部接口限频规则、Review 责任及计划记录字段。

- [ ] **Step 1: 更新 `SKILL.md`**

在 Review 规则中增加以下完整要求，并把“每个功能任务完成后测试”的流程改为按风险选择等级：

```markdown
测试等级：定向验证适用于单模块、低风险功能或明确修复；相关完整回归适用于跨模块、公共接口、安全或数据迁移，覆盖受影响模块、直接依赖、接口契约/集成测试及必要构建、类型或静态检查；全仓回归只适用于发布、全局基础设施或全局配置变更。

同一代码、依赖和运行配置未变化时，成功测试结果可复用为任务完成和提交前验证证据；只有受测代码、相关依赖、配置或测试环境变化后才重新运行对应验证。外部真实接口验证必须限频；失败后先记录和分析原因，不进行无条件自动重试。

Reviewer 默认审阅当前 diff 和已有测试结果，不重复执行测试；Review 检查需求与非目标、验收标准、改动范围与风险、测试等级和命令、结果证据以及失败/例外处理。仅在证据缺失或过期、结果与验收冲突，或属于相关完整回归、全仓回归或新发现高风险影响时补充验证。
```

- [ ] **Step 2: 更新根约束和个人约束模板**

将各模板的测试门禁替换为以下规则，并保留审批、范围检查和本地提交规则：

```markdown
按风险选择最小有效验证：定向验证用于单模块低风险改动；相关完整回归用于跨模块、公共接口、安全或数据迁移；全仓回归只用于发布、全局基础设施或全局配置变更。同一代码、依赖和运行配置未变化时，可复用成功测试证据，不重复执行相同验证。外部真实接口验证必须限频，失败后先分析原因，不进行无条件自动重试。

Review 检查需求、验收标准、改动范围与风险、测试等级、命令和结果证据；Reviewer 默认不重跑已有且未过期的测试，仅在证据缺失或过期、结果冲突或高风险影响时补充验证。
```

- [ ] **Step 3: 更新计划模板**

在现有 `Review 与批准记录` 中保留 `Tests` 字段以兼容 `check-plan`，并紧接其后增加：

```markdown
- Test level: `pending`
- Test commands and results: `-`
- Evidence validity: `-`
```

- [ ] **Step 4: 运行契约测试验证规则已满足**

Run: `python3 -m unittest tests.test_vteam.SkillContractTests -v`

Expected: PASS，新增三项契约测试和现有技能契约测试全部通过。

### Task 3: 验证模板一致性并交付

**Files:**
- Modify: `tests/test_vteam.py:822-968`
- Modify: `SKILL.md:89-125`
- Modify: `references/root-agents-template.md:10-18`
- Modify: `references/root-claude-template.md:10-18`
- Modify: `references/personal-agent-template.md:35-45`
- Modify: `references/plan-template.md:26-35`

**Interfaces:**
- Consumes: Task 1 与 Task 2 的实现。
- Produces: 可验证、无格式错误的技能更新。

- [ ] **Step 1: 运行完整仓库测试**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS，所有 V-Team 脚本和技能契约测试通过。

- [ ] **Step 2: 执行静态差异检查**

Run: `git diff --check HEAD`

Expected: exit 0，无空白或补丁格式错误。

- [ ] **Step 3: 人工核对设计覆盖**

核对设计文档中的三档测试策略、外部接口限频、证据复用、Review 结果导向以及不修改 `vteam.py` 五项要求，均能在 `SKILL.md` 和相应模板中找到。

- [ ] **Step 4: 提交变更**

```bash
git add SKILL.md references/root-agents-template.md references/root-claude-template.md \
  references/personal-agent-template.md references/plan-template.md tests/test_vteam.py \
  docs/superpowers/plans/2026-07-16-risk-based-testing-policy.md
git commit -m "规则：采用风险分级测试与结果导向 review"
```
