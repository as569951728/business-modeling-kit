"""Behavior checks for preservation, portability and false completion claims."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kit", ROOT / "kit.py")
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


class KitBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="business-model-kit-test-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "客户 A 带空格"

    def config(self):
        return kit.load_project(self.project)

    def write_config(self, config):
        (self.project / kit.MANIFEST).write_text(json.dumps(config), encoding="utf-8")

    def test_init_makes_no_completion_claim_or_adopted_model(self):
        kit.initialize(self.project, task="解释一次维修的交接")
        c = self.config()
        self.assertEqual(c["mode"], "plan")
        self.assertTrue(all(s["status"] == "not_started" for s in c["stages"].values()))
        self.assertFalse((self.project / "业务模型.md").exists())
        self.assertEqual(kit.project_issues(self.project, c), [])

    def test_repeated_init_preserves_work_task_and_agents(self):
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("# Existing rules\n保留这一条。\n")
        kit.initialize(self.project, task="原任务")
        p = self.project / "项目背景.md"
        p.write_text("已经填写的业务背景。")
        c = self.config()
        c["stages"]["S1"]["status"] = "in_progress"
        self.write_config(c)
        before = {p.name: p.read_bytes() for p in self.project.iterdir() if p.is_file()}
        kit.initialize(self.project, task="不得覆盖的新任务")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.project.iterdir() if p.is_file()})
        self.assertEqual((self.project / "AGENTS.md").read_text().count(kit.MARKER), 1)

    def test_missing_materials_do_not_create_project(self):
        with self.assertRaises(ValueError):
            kit.initialize(self.project, materials=Path(self.temp.name) / "missing")
        self.assertFalse(self.project.exists())

    def test_customer_project_cannot_be_inside_toolkit(self):
        with self.assertRaises(ValueError):
            kit.initialize(ROOT / "accidental-customer")
        self.assertFalse((ROOT / "accidental-customer").exists())

    def test_symlink_target_is_not_overwritten_or_followed(self):
        self.project.mkdir()
        outside = Path(self.temp.name) / "original.txt"
        outside.write_text("保留原文")
        (self.project / "项目背景.md").symlink_to(outside)
        with self.assertRaises(ValueError):
            kit.initialize(self.project)
        self.assertEqual(outside.read_text(), "保留原文")
        self.assertFalse((self.project / kit.MANIFEST).exists())

    def test_completed_step_needs_real_evidence_not_empty_template(self):
        kit.initialize(self.project)
        c = self.config()
        c["stages"]["plan"]["status"] = "done"
        self.assertTrue(any("没有证据" in e for e in kit.project_issues(self.project, c)))
        c["stages"]["plan"]["evidence"] = ["实施方案.md"]
        self.assertTrue(any("模板占位" in e for e in kit.project_issues(self.project, c)))
        (self.project / "实施方案.md").write_text("这里只表示已填写的计划，内容正确性另审。")
        self.assertEqual(kit.project_issues(self.project, c), [])

    def test_missing_evidence_and_skip_without_reason_are_reported(self):
        kit.initialize(self.project)
        c = self.config()
        c["stages"]["S2"] = {"status": "done", "evidence": ["missing.md"], "note": ""}
        c["stages"]["S6"] = {"status": "not_applicable", "evidence": [], "note": ""}
        issues = kit.project_issues(self.project, c)
        self.assertTrue(any("证据应定位" in e for e in issues))
        self.assertTrue(any("理由" in e for e in issues))

    def test_invalid_manifest_is_preserved(self):
        self.project.mkdir()
        p = self.project / kit.MANIFEST
        p.write_text("broken json")
        with self.assertRaises(ValueError):
            kit.initialize(self.project)
        self.assertEqual(p.read_text(), "broken json")

    def test_moved_or_missing_toolkit_is_reported(self):
        kit.initialize(self.project)
        c = self.config()
        c["kit_path"] = str(Path(self.temp.name) / "missing-kit")
        self.assertTrue(any("工具包位置失效" in e for e in kit.project_issues(self.project, c)))

    def test_non_dictionary_stage_does_not_crash_status(self):
        kit.initialize(self.project)
        c = self.config()
        c["stages"]["S1"] = 7
        self.write_config(c)
        r = subprocess.run([sys.executable, str(ROOT / "kit.py"), "status", str(self.project)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_non_string_status_does_not_crash(self):
        kit.initialize(self.project)
        c = self.config()
        c["stages"]["S1"]["status"] = ["done"]
        self.write_config(c)
        r = subprocess.run([sys.executable, str(ROOT / "kit.py"), "status", str(self.project)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_missing_version_has_a_clear_check_failure(self):
        copied = Path(self.temp.name) / "missing-version-kit"
        shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        (copied / "VERSION").unlink()
        r = subprocess.run([sys.executable, str(copied / "kit.py"), "check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("VERSION", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_materials_are_not_copied_to_project(self):
        material = Path(self.temp.name) / "访谈.txt"
        material.write_text("原始资料不复制")
        kit.initialize(self.project, materials=material)
        self.assertEqual(self.config()["materials"], [str(material.resolve())])
        self.assertFalse((self.project / material.name).exists())

    def test_portable_copy_and_broken_link_detection(self):
        copied = Path(self.temp.name) / "迁移后的工具包"
        shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.assertEqual(kit.package_issues(copied), [])
        (copied / "broken.md").write_text("[无法打开](missing-file.md)")
        self.assertTrue(any("missing-file.md" in e for e in kit.package_issues(copied)))


if __name__ == "__main__":
    unittest.main()
