"""V-Team 2.0 的角色路由、契约发现与轻量留档验收测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "scripts/vteam.py"
SKILL = REPOSITORY_ROOT / "SKILL.md"
REFERENCES = REPOSITORY_ROOT / "references"


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "product"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def state_path(self) -> Path:
        return self.project / ".vteam/state.json"

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def json_result(self, *arguments: str) -> dict:
        result = self.run_cli(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def read_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def publish(
        self,
        contract_id: str = "sandbox-api",
        status: str = "draft",
        consumer: str = "frontend-sandbox-console",
        capability: str = "sandbox-runtime",
        provider: str = "backend-sandbox-api",
    ) -> dict:
        return self.json_result(
            "contract",
            "publish",
            "--project-root",
            str(self.project),
            "--id",
            contract_id,
            "--capability",
            capability,
            "--provider",
            provider,
            "--consumer",
            consumer,
            "--source",
            "openapi",
            "--source-ref",
            "api/openapi.yaml#/sandbox",
            "--status",
            status,
            "--version",
            "1.0.0",
            "--mock",
            "fixtures/sandbox.json",
            "--json",
        )


class ContextTests(CliTestCase):
    def test_context_without_state_is_read_only(self) -> None:
        payload = self.json_result(
            "context",
            "--project-root",
            str(self.project),
            "--role-id",
            "frontend-sandbox-console",
            "--capability",
            "sandbox-runtime",
            "--json",
        )

        self.assertFalse(payload["state_exists"])
        self.assertEqual(payload["discipline"], "frontend")
        self.assertTrue(payload["role_reference"].endswith("references/role-frontend.md"))
        self.assertEqual(payload["contracts"], [])
        self.assertIsNone(payload["active"])
        self.assertFalse((self.project / ".vteam").exists())

    def test_context_returns_only_role_and_capability_relevant_records(self) -> None:
        self.publish()
        self.publish(
            contract_id="billing-api",
            consumer="frontend-billing-console",
            capability="billing",
            provider="backend-billing-api",
        )

        payload = self.json_result(
            "context",
            "--project-root",
            str(self.project),
            "--role-id",
            "frontend-sandbox-console",
            "--capability",
            "sandbox-runtime",
            "--json",
        )

        self.assertEqual([item["id"] for item in payload["contracts"]], ["sandbox-api"])
        self.assertNotIn("milestones", payload)

    def test_invalid_functional_role_is_rejected(self) -> None:
        result = self.run_cli(
            "context",
            "--project-root",
            str(self.project),
            "--role-id",
            "developer-1",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("角色 ID", result.stderr)
        self.assertFalse(self.state_path.exists())


class ContractLifecycleTests(CliTestCase):
    def test_publish_writes_compact_index_to_single_state_file(self) -> None:
        payload = self.publish(status="ready")
        contract = payload["contract"]

        self.assertEqual(contract["id"], "sandbox-api")
        self.assertEqual(contract["capability"], "sandbox-runtime")
        self.assertEqual(contract["consumers"], ["frontend-sandbox-console"])
        self.assertEqual(contract["source"], "openapi")
        self.assertEqual(contract["source_ref"], "api/openapi.yaml#/sandbox")
        self.assertNotIn("request", contract)
        self.assertNotIn("response", contract)
        self.assertEqual(
            [path.relative_to(self.project).as_posix() for path in self.project.rglob("*") if path.is_file()],
            [".vteam/state.json"],
        )

    def test_publish_updates_same_identity_but_cannot_rebind_it(self) -> None:
        self.publish()
        updated = self.publish(status="ready")
        self.assertEqual(updated["contract"]["status"], "ready")
        self.assertEqual(len(self.read_state()["contracts"]), 1)

        result = self.run_cli(
            "contract",
            "publish",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-api",
            "--capability",
            "another-capability",
            "--provider",
            "backend-sandbox-api",
            "--consumer",
            "frontend-sandbox-console",
            "--source",
            "openapi",
            "--source-ref",
            "api/openapi.yaml",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("不得改变 capability", result.stderr)

    def test_single_discovery_exposes_integration_gate(self) -> None:
        self.publish(status="draft")
        draft = self.json_result(
            "contract",
            "discover",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--consumer",
            "frontend-sandbox-console",
            "--json",
        )
        self.assertFalse(draft["contract"]["integration_allowed"])

        self.publish(status="ready")
        ready = self.json_result(
            "contract",
            "discover",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--consumer",
            "frontend-sandbox-console",
            "--json",
        )
        self.assertTrue(ready["contract"]["integration_allowed"])

    def test_no_discovery_is_explicit_blocker_and_does_not_write(self) -> None:
        result = self.run_cli(
            "contract",
            "discover",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--consumer",
            "frontend-sandbox-console",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("禁止猜测接口", result.stderr)
        self.assertFalse(self.state_path.exists())

    def test_multiple_discovery_requires_explicit_contract_id(self) -> None:
        self.publish(contract_id="sandbox-api-v1", status="ready")
        self.publish(contract_id="sandbox-api-v2", status="ready")
        ambiguous = self.run_cli(
            "contract",
            "discover",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--consumer",
            "frontend-sandbox-console",
        )
        self.assertEqual(ambiguous.returncode, 3)
        self.assertIn("sandbox-api-v1", ambiguous.stderr)
        self.assertIn("sandbox-api-v2", ambiguous.stderr)

        chosen = self.json_result(
            "contract",
            "discover",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--consumer",
            "frontend-sandbox-console",
            "--contract-id",
            "sandbox-api-v2",
            "--json",
        )
        self.assertEqual(chosen["contract"]["id"], "sandbox-api-v2")

    def test_verify_requires_ready_and_records_consumer_evidence(self) -> None:
        self.publish(status="draft")
        rejected = self.run_cli(
            "contract",
            "verify",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-api",
            "--verifier",
            "frontend-sandbox-console",
            "--evidence",
            "browser integration passed",
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("只有 ready", rejected.stderr)

        self.publish(status="ready")
        verified = self.json_result(
            "contract",
            "verify",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-api",
            "--verifier",
            "frontend-sandbox-console",
            "--evidence",
            "browser integration passed",
            "--json",
        )
        self.assertEqual(verified["contract"]["status"], "verified")
        self.assertEqual(
            verified["contract"]["verification"][-1]["by"],
            "frontend-sandbox-console",
        )

    def test_deprecated_contract_is_not_discoverable(self) -> None:
        self.publish(status="ready")
        self.json_result(
            "contract",
            "deprecate",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-api",
            "--reason",
            "replaced by v2",
            "--replacement",
            "sandbox-api-v2",
            "--json",
        )
        result = self.run_cli(
            "contract",
            "discover",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--consumer",
            "frontend-sandbox-console",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.read_state()["contracts"]["sandbox-api"]["status"], "deprecated")


class ResumeAndCompletionTests(CliTestCase):
    def set_resume(self, summary: str, next_step: str) -> dict:
        return self.json_result(
            "resume",
            "set",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--role",
            "backend-sandbox-api",
            "--summary",
            summary,
            "--next-step",
            next_step,
            "--reference",
            "api/openapi.yaml",
            "--json",
        )

    def test_resume_overwrites_one_current_record_per_capability(self) -> None:
        self.set_resume("first", "implement")
        self.set_resume("second", "verify")
        state = self.read_state()
        self.assertEqual(len(state["active"]), 1)
        self.assertEqual(state["active"]["sandbox-runtime"]["summary"], "second")
        self.assertEqual(state["active"]["sandbox-runtime"]["next_step"], "verify")

    def test_resume_clear_does_not_create_missing_state(self) -> None:
        payload = self.json_result(
            "resume",
            "clear",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--json",
        )
        self.assertFalse(payload["cleared"])
        self.assertFalse(self.state_path.exists())

    def test_module_completion_replaces_current_fact_and_clears_resume(self) -> None:
        self.publish(status="ready")
        self.set_resume("backend ready", "frontend integrate")
        payload = self.json_result(
            "module",
            "complete",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--summary",
            "sandbox lifecycle is usable",
            "--verification",
            "unit and integration tests passed",
            "--contract",
            "sandbox-api",
            "--json",
        )

        self.assertTrue(payload["cleared_active"])
        state = self.read_state()
        self.assertNotIn("sandbox-runtime", state["active"])
        self.assertEqual(state["capabilities"]["sandbox-runtime"]["status"], "completed")
        self.assertEqual(
            state["capabilities"]["sandbox-runtime"]["contracts"], ["sandbox-api"]
        )

    def test_module_completion_rejects_unstable_contract(self) -> None:
        self.publish(status="draft")
        result = self.run_cli(
            "module",
            "complete",
            "--project-root",
            str(self.project),
            "--capability",
            "sandbox-runtime",
            "--summary",
            "not actually complete",
            "--verification",
            "unit tests passed",
            "--contract",
            "sandbox-api",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ready 或 verified", result.stderr)
        self.assertNotIn("sandbox-runtime", self.read_state()["capabilities"])


class MilestoneTests(CliTestCase):
    def test_milestone_is_only_recorded_by_explicit_action_and_requires_reference(self) -> None:
        self.publish(status="ready")
        self.assertEqual(self.read_state()["milestones"], [])
        missing_reference = self.run_cli(
            "milestone",
            "record",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-v1",
            "--capability",
            "sandbox-runtime",
            "--summary",
            "first usable release",
        )
        self.assertEqual(missing_reference.returncode, 2)

        self.json_result(
            "milestone",
            "record",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-v1",
            "--capability",
            "sandbox-runtime",
            "--summary",
            "first usable release",
            "--reference",
            "git:abc123",
            "--json",
        )
        self.assertEqual(len(self.read_state()["milestones"]), 1)

    def test_context_and_milestone_list_do_not_load_reference_body(self) -> None:
        self.json_result(
            "milestone",
            "record",
            "--project-root",
            str(self.project),
            "--id",
            "sandbox-v1",
            "--capability",
            "sandbox-runtime",
            "--summary",
            "first usable release",
            "--reference",
            "adr/0001-secret-detail.md",
            "--json",
        )
        context = self.json_result(
            "context",
            "--project-root",
            str(self.project),
            "--role-id",
            "architect-sandbox-runtime",
            "--capability",
            "sandbox-runtime",
            "--json",
        )
        listing = self.json_result(
            "milestone",
            "list",
            "--project-root",
            str(self.project),
            "--json",
        )
        self.assertEqual(context["milestone_count"], 1)
        self.assertNotIn("adr/0001-secret-detail.md", json.dumps(context))
        self.assertNotIn("references", listing["milestones"][0])


class SkillContractTests(unittest.TestCase):
    def test_skill_is_explicit_and_uses_four_task_routes(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        interface = (REPOSITORY_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn("仅在用户明确调用 `$v-team`", skill)
        self.assertIn("allow_implicit_invocation: false", interface)
        for route in ("问答/分析", "快速改动", "标准功能", "重大改造"):
            self.assertIn(route, skill)

    def test_standard_feature_requires_value_architecture_and_user_approval(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        for requirement in (
            "用户问题、价值与使用频率",
            "现有能力能否复用",
            "可行性、约束、风险",
            "兼容/迁移/回滚",
            "明确请求用户确认该方案",
        ):
            self.assertIn(requirement, skill)
        self.assertIn("确认前", skill)
        self.assertIn("不得开始功能实现", skill)

    def test_role_playbooks_have_distinct_chains(self) -> None:
        expected = {
            "role-requirement.md": "不开发 / 复用 / 小改 / 新建",
            "role-architect.md": "组件关系、调用顺序、数据流",
            "role-backend.md": "契约优先",
            "role-frontend.md": "加载、空、成功、错误",
            "role-qa.md": "轻量风险矩阵",
        }
        for filename, marker in expected.items():
            self.assertIn(marker, (REFERENCES / filename).read_text(encoding="utf-8"))

    def test_contract_policy_prevents_frontend_guessing(self) -> None:
        policy = (REFERENCES / "contract-policy.md").read_text(encoding="utf-8")
        self.assertIn("capability", policy)
        self.assertIn("完整 consumer role ID", policy)
        self.assertIn("零个", policy)
        self.assertIn("多个", policy)
        self.assertIn("不得按相似名字", policy)
        self.assertIn("不保存接口正文", policy)

    def test_process_artifacts_are_not_required(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        milestone = (REFERENCES / "milestone-policy.md").read_text(encoding="utf-8")
        self.assertIn("不为问题、分析、方案草稿、日常测试或普通状态新建文件", skill)
        self.assertIn("不强制写 Markdown", milestone)
        self.assertIn("每个 capability 一条 active", milestone)
        self.assertIn("普通模块完成不生成总结文档", skill)

    def test_legacy_governance_templates_and_commands_are_removed(self) -> None:
        legacy_files = {
            "handoffs-template.md",
            "personal-agent-template.md",
            "plan-template.md",
            "project-template.md",
            "quick-onboarding-template.md",
            "root-agents-template.md",
            "root-claude-template.md",
            "team-template.json",
        }
        self.assertTrue(all(not (REFERENCES / name).exists() for name in legacy_files))
        help_result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(help_result.returncode, 0)
        for command in (
            "init",
            "agent",
            "check-plan",
            "check-scope",
            "cleanup",
            "handoff",
            "plan-git",
        ):
            self.assertNotIn(command, help_result.stdout)

    def test_skill_is_progressively_loaded_and_compact(self) -> None:
        skill_lines = SKILL.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(skill_lines), 500)
        self.assertIn("只读取对应参考", "\n".join(skill_lines))
        expected = {
            "role-router.md",
            "role-requirement.md",
            "role-architect.md",
            "role-backend.md",
            "role-frontend.md",
            "role-qa.md",
            "contract-policy.md",
            "milestone-policy.md",
        }
        self.assertEqual({path.name for path in REFERENCES.iterdir()}, expected)


if __name__ == "__main__":
    unittest.main()
