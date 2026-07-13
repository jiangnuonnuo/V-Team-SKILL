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


if __name__ == "__main__":
    unittest.main()
