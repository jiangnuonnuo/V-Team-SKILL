"""description: 验证 V-Team 统一命令行入口的项目初始化、身份约束、范围检查与清理行为。"""

from __future__ import annotations

import json
import importlib.util
import locale
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "vteam.py"


def load_vteam_module() -> types.ModuleType:
    """description: 动态加载统一入口模块；输入为固定脚本路径；输出为可直接测试的模块对象。"""
    specification = importlib.util.spec_from_file_location("vteam_under_test", SCRIPT_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"无法加载测试模块: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class VTeamTestCase(unittest.TestCase):
    """description: 为 V-Team CLI 测试提供隔离项目目录和命令执行辅助能力。"""

    def setUp(self) -> None:
        """description: 为单个测试创建临时项目目录；输入为 unittest 生命周期；输出为可用的 project_root。"""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name) / "示例 项目"
        self.project_root.mkdir(parents=True)

    def tearDown(self) -> None:
        """description: 清理单个测试的临时目录；输入为 setUp 创建的目录；输出为空。"""
        self.temporary_directory.cleanup()

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """description: 运行 V-Team CLI；输入为命令参数；输出为包含退出码和文本输出的完成结果。"""
        command = [sys.executable, str(SCRIPT_PATH), *arguments]
        return subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False),
        )

    def initialize(self, *runtimes: str) -> subprocess.CompletedProcess[str]:
        """description: 初始化临时项目；输入为运行端列表；输出为 CLI 完成结果。"""
        arguments = ["init", "--project-root", str(self.project_root)]
        for runtime in runtimes:
            arguments.extend(["--runtime", runtime])
        return self.run_cli(*arguments)

    def register_agent(
        self,
        agent_id: str,
        runtime: str = "codex",
        role: str = "backend",
    ) -> subprocess.CompletedProcess[str]:
        """description: 注册测试 Agent；输入为身份、运行端和角色；输出为 CLI 完成结果。"""
        return self.run_cli(
            "agent",
            "--project-root",
            str(self.project_root),
            "--agent-id",
            agent_id,
            "--runtime",
            runtime,
            "--role",
            role,
            "--responsibility",
            "用户与权限模块",
            "--module",
            "backend/auth",
            "--allow",
            "backend/auth/",
            "--allow",
            "tests/auth/",
            "--read-doc",
            "Plan/collaboration/api-contracts.md",
        )

    def read_team(self) -> dict[str, object]:
        """description: 读取临时项目的团队配置；输入为 project_root；输出为解析后的 JSON 对象。"""
        team_path = self.project_root / "Plan" / "team.json"
        return json.loads(team_path.read_text(encoding="utf-8"))

    def run_git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """description: 在临时项目运行 Git；输入为 Git 参数；输出为包含退出码与文本的完成结果。"""
        return subprocess.run(
            ["git", *arguments],
            cwd=self.project_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def initialize_git_repository(self) -> None:
        """description: 把当前临时项目初始化为含基线提交的 Git 仓库；输入为 project_root；输出为空。"""
        commands = [
            ("init",),
            ("config", "user.name", "V-Team Test"),
            ("config", "user.email", "vteam-test@example.com"),
            ("config", "commit.gpgsign", "false"),
            ("add", "."),
            ("commit", "-m", "初始化测试项目"),
        ]
        for arguments in commands:
            result = self.run_git(*arguments)
            self.assertEqual(0, result.returncode, result.stderr)


class InitializationTests(VTeamTestCase):
    """description: 验证无版本项目结构与 Codex、Claude 根约束文件生成规则。"""

    def test_codex_init_creates_only_codex_root_file(self) -> None:
        """description: 输入 Codex 运行端；输出仅包含 AGENTS.md 根入口。"""
        result = self.initialize("codex")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.project_root / "AGENTS.md").is_file())
        self.assertFalse((self.project_root / "CLAUDE.md").exists())

    def test_claude_init_creates_only_claude_root_file(self) -> None:
        """description: 输入 Claude 运行端；输出仅包含 CLAUDE.md 根入口。"""
        result = self.initialize("claude")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.project_root / "CLAUDE.md").is_file())
        self.assertFalse((self.project_root / "AGENTS.md").exists())

    def test_mixed_init_creates_both_root_files(self) -> None:
        """description: 输入混合运行端；输出同时包含 Codex 与 Claude 根入口。"""
        result = self.initialize("codex", "claude")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.project_root / "AGENTS.md").is_file())
        self.assertTrue((self.project_root / "CLAUDE.md").is_file())

    def test_init_never_creates_versions_directory(self) -> None:
        """description: 输入任意合法运行端；输出不得包含 Plan/versions 版本目录。"""
        result = self.initialize("codex")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.project_root / "Plan" / "versions").exists())
        self.assertTrue((self.project_root / "Plan" / "project.md").is_file())
        self.assertTrue((self.project_root / "Plan" / "team.json").is_file())
        self.assertTrue((self.project_root / "Plan" / "collaboration" / "architecture.md").is_file())
        self.assertTrue((self.project_root / "Plan" / "collaboration" / "api-contracts.md").is_file())
        self.assertTrue((self.project_root / "Plan" / "collaboration" / "handoffs.md").is_file())

    def test_root_rules_contain_required_behavior_gates(self) -> None:
        """description: 输入 Codex 项目；输出根规则包含身份、审批、测试、提交和上下文门禁。"""
        result = self.initialize("codex")
        self.assertEqual(0, result.returncode, result.stderr)

        rules = (self.project_root / "AGENTS.md").read_text(encoding="utf-8")
        required_fragments = [
            "无法确定 `agent-id`",
            "Plan/agents/<agent-id>/AGENT.md",
            "用户批准",
            "测试通过",
            "禁止自行推送远程",
            "禁止自行合并",
            "Plan/archive/",
            "completed",
            "abandoned",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, rules)


class AgentRegistrationTests(VTeamTestCase):
    """description: 验证 Agent 身份、职责、白名单和运行端入口的同步生成。"""

    def test_register_agents_with_same_role_keeps_separate_identity_files(self) -> None:
        """description: 输入同角色不同 ID；输出独立配置记录和独立个人目录。"""
        self.assertEqual(0, self.initialize("codex").returncode)

        first_result = self.register_agent("backend-1")
        second_result = self.register_agent("backend-2")

        self.assertEqual(0, first_result.returncode, first_result.stderr)
        self.assertEqual(0, second_result.returncode, second_result.stderr)
        team = self.read_team()
        agent_ids = [agent["id"] for agent in team["agents"]]
        self.assertEqual(["backend-1", "backend-2"], agent_ids)
        self.assertTrue((self.project_root / "Plan" / "agents" / "backend-1" / "AGENT.md").is_file())
        self.assertTrue((self.project_root / "Plan" / "agents" / "backend-2" / "AGENT.md").is_file())

    def test_register_agent_writes_identity_scope_and_required_reads(self) -> None:
        """description: 输入完整 Agent 配置；输出个人规则包含身份、职责、白名单和必读文档。"""
        self.assertEqual(0, self.initialize("codex").returncode)

        result = self.register_agent("backend-1")

        self.assertEqual(0, result.returncode, result.stderr)
        agent_root = self.project_root / "Plan" / "agents" / "backend-1"
        rules = (agent_root / "AGENT.md").read_text(encoding="utf-8")
        self.assertIn("backend-1", rules)
        self.assertIn("用户与权限模块", rules)
        self.assertIn("backend/auth/", rules)
        self.assertIn("Plan/collaboration/api-contracts.md", rules)
        self.assertIn("一次性授权", rules)
        self.assertTrue((agent_root / "PLAN.md").is_file())

    def test_register_agent_updates_runtime_root_files(self) -> None:
        """description: 输入新增 Claude Agent；输出追加 Claude 运行端并生成对应根入口。"""
        self.assertEqual(0, self.initialize("codex").returncode)

        result = self.register_agent("frontend-1", runtime="claude", role="frontend")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.project_root / "AGENTS.md").is_file())
        self.assertTrue((self.project_root / "CLAUDE.md").is_file())
        self.assertEqual(["codex", "claude"], self.read_team()["runtimes"])

    def test_invalid_team_configuration_reports_exact_field(self) -> None:
        """description: 输入 agents 类型错误的配置；输出退出码 1 和明确字段错误。"""
        self.assertEqual(0, self.initialize("codex").returncode)
        team_path = self.project_root / "Plan" / "team.json"
        team_path.write_text(
            json.dumps(
                {
                    "project_name": "示例项目",
                    "runtimes": ["codex"],
                    "agents": "invalid",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.register_agent("backend-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("agents", result.stderr)


class ScopeCheckTests(VTeamTestCase):
    """description: 验证提交前单次 Git 差异读取、路径规范化和白名单越界报告。"""

    def test_paths_inside_whitelist_pass(self) -> None:
        """description: 输入白名单内暂存文件；输出范围检查通过且退出码为 0。"""
        self.assertEqual(0, self.initialize("codex").returncode)
        self.assertEqual(0, self.register_agent("backend-1").returncode)
        self.initialize_git_repository()
        target_path = self.project_root / "backend" / "auth" / "service.py"
        target_path.parent.mkdir(parents=True)
        target_path.write_text("VALUE = 1\n", encoding="utf-8")
        self.assertEqual(0, self.run_git("add", ".").returncode)

        result = self.run_cli(
            "check-scope",
            "--project-root",
            str(self.project_root),
            "--agent-id",
            "backend-1",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("范围检查通过", result.stdout)

    def test_paths_outside_whitelist_are_reported(self) -> None:
        """description: 输入白名单内外混合暂存文件；输出只列出越界路径并返回 2。"""
        self.assertEqual(0, self.initialize("codex").returncode)
        self.assertEqual(0, self.register_agent("backend-1").returncode)
        self.initialize_git_repository()
        allowed_path = self.project_root / "backend" / "auth" / "service.py"
        denied_path = self.project_root / "frontend" / "login.ts"
        allowed_path.parent.mkdir(parents=True)
        denied_path.parent.mkdir(parents=True)
        allowed_path.write_text("VALUE = 1\n", encoding="utf-8")
        denied_path.write_text("export const login = true;\n", encoding="utf-8")
        self.assertEqual(0, self.run_git("add", ".").returncode)

        result = self.run_cli(
            "check-scope",
            "--project-root",
            str(self.project_root),
            "--agent-id",
            "backend-1",
        )

        output = result.stdout + result.stderr
        self.assertEqual(2, result.returncode, output)
        self.assertIn("frontend/login.ts", output)
        self.assertNotIn("backend/auth/service.py", output)
        self.assertIn("一次性授权", output)
        self.assertIn("不会扩大永久白名单", output)

    def test_backslashes_spaces_and_non_ascii_paths_are_normalized(self) -> None:
        """description: 输入反斜杠、空格和中文路径；输出为规范 Git 相对路径并可匹配目录规则。"""
        module = load_vteam_module()
        normalize = getattr(module, "normalize_relative_path", None)
        matcher = getattr(module, "path_is_allowed", None)
        self.assertIsNotNone(normalize, "缺少 normalize_relative_path")
        self.assertIsNotNone(matcher, "缺少 path_is_allowed")

        normalized = normalize(".\\后端\\用户 模块\\服务.py")

        self.assertEqual("后端/用户 模块/服务.py", normalized)
        self.assertTrue(matcher(normalized, ["后端/用户 模块/"]))

    def test_case_insensitive_matching_can_model_windows(self) -> None:
        """description: 输入大小写不同的 Windows 模拟路径；输出为允许匹配。"""
        module = load_vteam_module()
        matcher = getattr(module, "path_is_allowed", None)
        self.assertIsNotNone(matcher, "缺少 path_is_allowed")

        self.assertTrue(
            matcher("Backend/API.py", ["backend/"], case_sensitive=False)
        )
        self.assertFalse(
            matcher("Backend/API.py", ["backend/"], case_sensitive=True)
        )

    def test_exact_directory_and_glob_rules_have_distinct_semantics(self) -> None:
        """description: 输入精确文件、目录和 glob；输出遵循各自匹配语义。"""
        module = load_vteam_module()
        matcher = getattr(module, "path_is_allowed", None)
        self.assertIsNotNone(matcher, "缺少 path_is_allowed")

        self.assertTrue(matcher("README.md", ["README.md"]))
        self.assertFalse(matcher("docs/README.md", ["README.md"]))
        self.assertTrue(matcher("backend/auth/service.py", ["backend/"]))
        self.assertTrue(matcher("backend/auth/service.py", ["backend/**"]))
        self.assertTrue(matcher("frontend/login.ts", ["frontend/*.ts"]))
        self.assertFalse(matcher("frontend/nested/login.ts", ["frontend/*.ts"]))
        self.assertTrue(matcher("any/path.txt", ["."]))

    def test_path_escape_and_absolute_paths_are_rejected(self) -> None:
        """description: 输入路径逃逸和绝对路径；输出为 ValueError。"""
        module = load_vteam_module()
        normalize = getattr(module, "normalize_relative_path", None)
        self.assertIsNotNone(normalize, "缺少 normalize_relative_path")

        invalid_paths = ["../secret.txt", "C:\\secret.txt", "/tmp/secret.txt"]
        for invalid_path in invalid_paths:
            with self.assertRaises(ValueError):
                normalize(invalid_path)

    def test_git_quoted_utf8_path_is_decoded(self) -> None:
        """description: 输入 Git C 风格八进制中文路径；输出为真实 UTF-8 相对路径。"""
        module = load_vteam_module()
        decoder = getattr(module, "decode_git_path", None)
        self.assertIsNotNone(decoder, "缺少 decode_git_path")

        decoded = decoder('"docs/\\346\\226\\207\\346\\241\\243.md"')

        self.assertEqual("docs/文档.md", decoded)

    def test_one_time_approval_is_never_persisted_to_team_json(self) -> None:
        """description: 输入越界检查；输出只报告授权流程且团队配置字节保持不变。"""
        self.assertEqual(0, self.initialize("codex").returncode)
        self.assertEqual(0, self.register_agent("backend-1").returncode)
        self.initialize_git_repository()
        team_path = self.project_root / "Plan" / "team.json"
        before_content = team_path.read_bytes()
        denied_path = self.project_root / "frontend" / "越界 文件.ts"
        denied_path.parent.mkdir(parents=True)
        denied_path.write_text("export const value = 1;\n", encoding="utf-8")
        self.assertEqual(0, self.run_git("add", ".").returncode)

        result = self.run_cli(
            "check-scope",
            "--project-root",
            str(self.project_root),
            "--agent-id",
            "backend-1",
        )

        output = result.stdout + result.stderr
        self.assertEqual(2, result.returncode, output)
        self.assertIn("frontend/", output)
        self.assertIn("一次性授权", output)
        self.assertEqual(before_content, team_path.read_bytes())
        self.assertNotIn("approval", team_path.read_text(encoding="utf-8"))

    def test_git_diff_uses_name_only_head_once(self) -> None:
        """description: 输入项目路径；输出只调用一次固定参数数组的 Git 差异命令。"""
        module = load_vteam_module()
        collector = getattr(module, "collect_git_changes", None)
        self.assertIsNotNone(collector, "缺少 collect_git_changes")
        completed = subprocess.CompletedProcess(
            args=["git", "diff", "--name-only", "HEAD"],
            returncode=0,
            stdout="backend/auth/service.py\n",
            stderr="",
        )

        with mock.patch.object(module.subprocess, "run", return_value=completed) as runner:
            paths = collector(self.project_root)

        self.assertEqual(["backend/auth/service.py"], paths)
        runner.assert_called_once_with(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=self.project_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


class CleanupTests(VTeamTestCase):
    """description: 验证完成或废弃计划的证据校验、归档、重置和 handoff 清理。"""

    def setUp(self) -> None:
        """description: 初始化已注册 backend-1 的临时项目；输入为 unittest 生命周期；输出为可写计划。"""
        super().setUp()
        self.assertEqual(0, self.initialize("codex").returncode)
        self.assertEqual(0, self.register_agent("backend-1").returncode)

    @property
    def plan_path(self) -> Path:
        """description: 获取当前 Agent 活动计划路径；输入为 project_root；输出为 PLAN.md 路径。"""
        return self.project_root / "Plan" / "agents" / "backend-1" / "PLAN.md"

    @property
    def handoffs_path(self) -> Path:
        """description: 获取项目活动 handoff 路径；输入为 project_root；输出为 handoffs.md 路径。"""
        return self.project_root / "Plan" / "collaboration" / "handoffs.md"

    def build_plan(
        self,
        status: str,
        task_rows: list[tuple[str, str, str, str, str]],
        reason: str = "无。",
        approval: str = "approved",
    ) -> str:
        """description: 构造清理测试计划；输入为状态、任务、原因和审批；输出为完整 Markdown。"""
        rows = "\n".join(
            f"| {task_id} | {summary} | {task_status} | {test_result} | {commit_hash} |"
            for task_id, summary, task_status, test_result, commit_hash in task_rows
        )
        return (
            "# backend-1 活动计划\n\n"
            "- Agent ID: `backend-1`\n"
            f"- Status: `{status}`\n"
            f"- Approval: `{approval}`\n\n"
            "## 当前目标\n\n"
            "完成权限功能。\n\n"
            "## 功能任务\n\n"
            "| ID | 完整功能或明确修复 | 状态 | 测试结果 | 本地提交 |\n"
            "|---|---|---|---|---|\n"
            f"{rows}\n\n"
            "## 放弃原因\n\n"
            f"- {reason}\n\n"
            "## 整体完成结论\n\n"
            "- 已记录。\n"
        )

    def write_plan(
        self,
        status: str,
        task_rows: list[tuple[str, str, str, str, str]],
        reason: str = "无。",
        approval: str = "approved",
    ) -> None:
        """description: 写入清理测试计划；输入为计划字段；输出为空。"""
        content = self.build_plan(status, task_rows, reason, approval)
        self.plan_path.write_text(content, encoding="utf-8", newline="\n")

    def run_cleanup(self) -> subprocess.CompletedProcess[str]:
        """description: 运行 backend-1 清理命令；输入为固定身份；输出为 CLI 完成结果。"""
        return self.run_cli(
            "cleanup",
            "--project-root",
            str(self.project_root),
            "--agent-id",
            "backend-1",
        )

    def test_draft_and_in_progress_plans_cannot_be_cleaned(self) -> None:
        """description: 输入 draft 与 in-progress 计划；输出均拒绝且原计划不变。"""
        for status in ["draft", "in-progress"]:
            with self.subTest(status=status):
                self.write_plan(status, [])
                original_content = self.plan_path.read_text(encoding="utf-8")

                result = self.run_cleanup()

                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn(status, result.stderr)
                self.assertEqual(
                    original_content,
                    self.plan_path.read_text(encoding="utf-8"),
                )

    def test_completed_plan_requires_tasks_tests_and_commit_hashes(self) -> None:
        """description: 输入完成证据缺失的计划；输出拒绝并指出证据问题。"""
        invalid_cases = [
            ("缺少任务", []),
            ("缺少测试", [("T1", "权限功能", "completed", "-", "abcdef1")]),
            ("缺少提交", [("T1", "权限功能", "completed", "OK", "-")]),
            ("任务未完成", [("T1", "权限功能", "pending", "OK", "abcdef1")]),
        ]
        for label, task_rows in invalid_cases:
            with self.subTest(label=label):
                self.write_plan("completed", task_rows)

                result = self.run_cleanup()

                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn("错误", result.stderr)
                self.assertFalse(any((self.project_root / "Plan" / "archive").iterdir()))

    def test_abandoned_plan_can_be_archived_with_reason(self) -> None:
        """description: 输入含放弃原因的 abandoned 计划；输出归档成功；缺少原因时拒绝。"""
        self.write_plan("abandoned", [], reason="用户取消该需求。")

        accepted_result = self.run_cleanup()

        self.assertEqual(0, accepted_result.returncode, accepted_result.stderr)
        archive_files = list((self.project_root / "Plan" / "archive").glob("*.md"))
        self.assertEqual(1, len(archive_files))
        self.assertIn("用户取消该需求", archive_files[0].read_text(encoding="utf-8"))

        self.write_plan("abandoned", [], reason="无。")
        rejected_result = self.run_cleanup()
        self.assertEqual(1, rejected_result.returncode)
        self.assertIn("放弃原因", rejected_result.stderr)

    def test_completed_plan_is_archived_and_active_plan_is_reset(self) -> None:
        """description: 输入证据完整的完成计划；输出保留快照并重置为空白草稿。"""
        self.write_plan(
            "completed",
            [("T1", "完成权限功能", "completed", "9 tests OK", "abcdef1")],
        )

        result = self.run_cleanup()

        self.assertEqual(0, result.returncode, result.stderr)
        archive_files = list((self.project_root / "Plan" / "archive").glob("*.md"))
        self.assertEqual(1, len(archive_files))
        archive_content = archive_files[0].read_text(encoding="utf-8")
        self.assertIn("完成权限功能", archive_content)
        self.assertIn("9 tests OK", archive_content)
        self.assertIn("abcdef1", archive_content)
        active_content = self.plan_path.read_text(encoding="utf-8")
        self.assertIn("- Status: `draft`", active_content)
        self.assertIn("当前无活动任务", active_content)
        self.assertNotIn("完成权限功能", active_content)

    def test_closed_handoffs_are_archived_and_removed_from_active_file(self) -> None:
        """description: 输入已关闭和无关开放 handoff；输出关闭项归档移除且开放项保留。"""
        self.write_plan(
            "completed",
            [("T1", "完成接口", "completed", "API test OK", "1234567")],
        )
        handoffs = (
            "# 当前跨 Agent 对接\n\n"
            "| ID | 提出者 | 接收者 | 交付物 | 验收条件 | 状态 |\n"
            "|---|---|---|---|---|---|\n"
            "| H1 | backend-1 | frontend-1 | 登录接口 | 联调通过 | completed |\n"
            "| H2 | backend-1 | tester-1 | 旧方案 | 无 | cancelled |\n"
            "| H3 | data-1 | report-1 | 报表 | 页面可见 | open |\n"
        )
        self.handoffs_path.write_text(handoffs, encoding="utf-8", newline="\n")

        result = self.run_cleanup()

        self.assertEqual(0, result.returncode, result.stderr)
        active_handoffs = self.handoffs_path.read_text(encoding="utf-8")
        self.assertNotIn("H1", active_handoffs)
        self.assertNotIn("H2", active_handoffs)
        self.assertIn("H3", active_handoffs)
        archive_content = next(
            (self.project_root / "Plan" / "archive").glob("*.md")
        ).read_text(encoding="utf-8")
        self.assertIn("H1", archive_content)
        self.assertIn("H2", archive_content)

    def test_open_handoff_involving_agent_blocks_completed_cleanup(self) -> None:
        """description: 输入当前 Agent 参与的开放 handoff；输出拒绝完成计划清理。"""
        self.write_plan(
            "completed",
            [("T1", "完成接口", "completed", "API test OK", "1234567")],
        )
        handoffs = (
            "# 当前跨 Agent 对接\n\n"
            "| ID | 提出者 | 接收者 | 交付物 | 验收条件 | 状态 |\n"
            "|---|---|---|---|---|---|\n"
            "| H1 | backend-1 | frontend-1 | 登录接口 | 联调通过 | open |\n"
        )
        self.handoffs_path.write_text(handoffs, encoding="utf-8", newline="\n")
        original_plan = self.plan_path.read_text(encoding="utf-8")

        result = self.run_cleanup()

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("H1", result.stderr)
        self.assertEqual(original_plan, self.plan_path.read_text(encoding="utf-8"))

    def test_unknown_handoff_status_blocks_cleanup(self) -> None:
        """description: 输入未知 handoff 状态；输出拒绝清理，避免把不完整契约推断为关闭。"""
        self.write_plan(
            "completed",
            [("T1", "完成接口", "completed", "API test OK", "1234567")],
        )
        handoffs = (
            "# 当前跨 Agent 对接\n\n"
            "| ID | 提出者 | 接收者 | 交付物 | 验收条件 | 状态 |\n"
            "|---|---|---|---|---|---|\n"
            "| H1 | backend-1 | frontend-1 | 登录接口 | 联调通过 | waiting |\n"
        )
        self.handoffs_path.write_text(handoffs, encoding="utf-8", newline="\n")

        result = self.run_cleanup()

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("未知状态", result.stderr)
        self.assertIn("H1", self.handoffs_path.read_text(encoding="utf-8"))

    def test_archive_name_collision_creates_deterministic_suffix(self) -> None:
        """description: 输入已存在的同日归档；输出新归档使用 -2 且不覆盖旧文件。"""
        self.write_plan(
            "completed",
            [("T1", "完成权限功能", "completed", "OK", "abcdef1")],
        )
        archive_root = self.project_root / "Plan" / "archive"
        first_archive = archive_root / f"{date.today().isoformat()}-backend-1-plan.md"
        first_archive.write_text("旧归档\n", encoding="utf-8")

        result = self.run_cleanup()

        self.assertEqual(0, result.returncode, result.stderr)
        second_archive = archive_root / f"{date.today().isoformat()}-backend-1-plan-2.md"
        self.assertTrue(second_archive.is_file())
        self.assertEqual("旧归档\n", first_archive.read_text(encoding="utf-8"))


class SkillContractTests(VTeamTestCase):
    """description: 验证技能触发信息、强制工作流、资源清理和技能库索引保持一致。"""

    def test_skill_description_matches_multi_agent_project_workflow(self) -> None:
        """description: 输入技能 frontmatter；输出为只描述触发条件的多 Agent 项目协作说明。"""
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")
        description_line = next(
            line for line in content.splitlines() if line.startswith("description:")
        )

        self.assertTrue(description_line.startswith("description: Use when"))
        for keyword in ["Codex", "Claude", "multi-agent", "module ownership"]:
            self.assertIn(keyword, description_line)
        self.assertNotIn("versioned", description_line.lower())
        self.assertLessEqual(len(content.splitlines()), 500)

    def test_skill_requires_identity_personal_agent_and_plan_approval(self) -> None:
        """description: 输入技能正文；输出明确身份、个人规则和用户审批三道实现门禁。"""
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_fragments = [
            "身份不明确时停止并询问用户",
            "Plan/agents/<agent-id>/AGENT.md",
            "强制读取",
            "waiting-approval",
            "用户批准前禁止实现代码",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, content)

    def test_skill_documents_single_pre_commit_scope_check(self) -> None:
        """description: 输入技能正文；输出只在本地提交前执行一次固定差异检查。"""
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("只在本地提交前统一检查一次", content)
        self.assertIn("git diff --name-only HEAD", content)
        self.assertNotIn("每次修改文件前", content)
        self.assertNotIn("Git Hook", content)

    def test_skill_allows_user_approved_cross_module_commit(self) -> None:
        """description: 输入技能正文；输出允许跨模块工作并要求本次提交的一次性用户授权。"""
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("允许跨模块", content)
        self.assertIn("一次性授权", content)
        self.assertIn("当前提交", content)
        self.assertIn("不得修改 `Plan/team.json`", content)

    def test_skill_forbids_remote_push_and_self_merge_without_managing_branches(self) -> None:
        """description: 输入技能正文；输出禁止远程推送合并且不包含分支管理流程。"""
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("禁止自行推送远程", content)
        self.assertIn("禁止自行合并", content)
        self.assertIn("不创建、切换、命名或管理 Git 分支", content)
        self.assertNotIn("branch naming", content.lower())

    def test_skill_documents_living_collaboration_and_cleanup_rules(self) -> None:
        """description: 输入技能正文；输出为三份当前态协作文档和安全归档清理规则。"""
        content = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_fragments = [
            "Plan/collaboration/architecture.md",
            "Plan/collaboration/api-contracts.md",
            "Plan/collaboration/handoffs.md",
            "覆盖或修订",
            "completed",
            "abandoned",
            "Plan/archive/",
            "默认忽略归档",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, content)

    def test_old_scripts_and_version_templates_are_removed(self) -> None:
        """description: 输入重构后的技能目录；输出只保留统一入口和新当前态模板。"""
        old_paths = [
            "scripts/init_project.py",
            "scripts/register_agent.py",
            "scripts/run_manager_cycle.py",
            "scripts/update_agent_status.py",
            "scripts/update_review.py",
            "references/agent-card-template.md",
            "references/memory-rules.md",
            "references/next-steps-template.md",
            "references/product-report-template.md",
            "references/review-template.md",
            "references/verification-template.md",
            "references/work-template.md",
        ]
        for relative_path in old_paths:
            self.assertFalse((REPOSITORY_ROOT / relative_path).exists(), relative_path)
        self.assertTrue((REPOSITORY_ROOT / "scripts" / "vteam.py").is_file())

    def test_repository_readme_documents_cross_platform_usage(self) -> None:
        """description: 输入仓库说明；输出包含新用途和跨平台命令，不依赖仓库外路径。"""
        repository_readme_path = REPOSITORY_ROOT / "README.md"
        self.assertTrue(repository_readme_path.is_file(), "仓库缺少 README.md")
        repository_readme = repository_readme_path.read_text(encoding="utf-8")

        for fragment in ["Windows", "macOS", "scripts/vteam.py", "check-scope", "cleanup"]:
            self.assertIn(fragment, repository_readme)
        self.assertIn("Python 3.10", repository_readme)

    def test_openai_interface_matches_new_skill(self) -> None:
        """description: 输入 agents/openai.yaml；输出为新技能展示信息和显式技能调用提示。"""
        content = (REPOSITORY_ROOT / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn('display_name: "V-Team Project Collaboration"', content)
        self.assertIn("$project-harness-lite", content)
        self.assertNotIn("version", content.lower())
        self.assertNotIn("manager cycle", content.lower())


if __name__ == "__main__":
    unittest.main()
