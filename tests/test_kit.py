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
        c["stages"]["plan"]["completed"] = "本轮任务和各步完成标准已写入方案。"
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

    def evidence(self):
        (self.project / "核查依据.md").write_text("单元测试的模拟证据，只测试登记行为，不是客户验收。")
        return ["核查依据.md"]

    def test_step_order_does_not_skip_blocked_work_for_a_later_active_step(self):
        kit.initialize(self.project, mode="execute", scope=["S1", "S2", "S3"])
        kit.update_stage(self.project, "S1", "blocked", note="缺一份原件", remaining="取得原件", needs_from="资料提供者")
        kit.update_stage(self.project, "S3", "in_progress", completed="仅整理已有候选的草稿")
        c = self.config()
        self.assertEqual(kit.workflow_position(c), ("S1", "S2"))
        report = kit.render_progress(self.project, c)
        self.assertIn("当前：S1", report)
        self.assertIn("先解决：取得原件", report)
        self.assertIn("目前未自动进入", report)

    def test_recorded_completion_advances_but_waiting_review_does_not(self):
        kit.initialize(self.project, mode="execute", scope=["S1", "S2"])
        kit.update_stage(self.project, "S1", "awaiting_review", note="需核对阅读范围", remaining="核对遗漏")
        self.assertEqual(kit.workflow_position(self.config())[0], "S1")
        kit.update_stage(self.project, "S1", "done", completed="范围和缺口核查已记录", remaining="", note="",
                         evidence=self.evidence())
        self.assertEqual(kit.workflow_position(self.config())[0], "S2")
        self.assertIn("当前：S2", (self.project / kit.PROGRESS).read_text())
        self.assertEqual(len(self.config()["progress_history"]), 2)

    def test_completion_with_remaining_work_is_rejected_without_writing(self):
        kit.initialize(self.project, scope=["S1"])
        original = (self.project / kit.MANIFEST).read_bytes()
        with self.assertRaises(ValueError):
            kit.update_stage(self.project, "S1", "done", completed="部分已读", remaining="仍有未读原件",
                             evidence=self.evidence())
        self.assertEqual((self.project / kit.MANIFEST).read_bytes(), original)

    def test_plan_only_round_closes_without_starting_model_execution(self):
        kit.initialize(self.project)
        kit.update_stage(self.project, "plan", "done", completed="已记录本轮方案", evidence=self.evidence())
        report = kit.render_progress(self.project, self.config())
        self.assertIn("本轮收尾与接续", report)
        self.assertNotIn("当前：S1", report)
        self.assertEqual(self.config()["stages"]["S1"]["status"], "not_started")
        with self.assertRaises(ValueError):
            kit.update_stage(self.project, "S1", "in_progress")

    def test_reopening_invalidates_later_completion_and_preserves_history(self):
        kit.initialize(self.project, mode="execute")
        for k in ("S2", "S3", "S5"):
            kit.update_stage(self.project, k, "done", completed="模拟已核结果", evidence=self.evidence())
        kit.update_stage(self.project, "S6", "not_applicable", note="当时无修订")
        kit.update_stage(self.project, "S2", "needs_recheck", note="新材料改变原定义", remaining="重核定义")
        c = self.config()
        for k in ("S3", "S5", "S6"):
            self.assertEqual(c["stages"][k]["status"], "needs_recheck")
        self.assertEqual(c["stages"]["S5"]["evidence"], ["核查依据.md"])
        self.assertEqual(c["progress_history"][-1]["downstream_before_recheck"]["S6"]["status"], "not_applicable")

    def test_changed_completed_basis_rechecks_downstream(self):
        kit.initialize(self.project, mode="execute", scope=["S3", "S5"])
        for k in ("S3", "S5"):
            kit.update_stage(self.project, k, "done", completed="原版结果", evidence=self.evidence())
        kit.update_stage(self.project, "S3", "done", completed="模型依据已更新并复核", evidence=self.evidence())
        self.assertEqual(self.config()["stages"]["S5"]["status"], "needs_recheck")

    def test_manual_progress_edits_are_not_overwritten_and_manifest_is_preserved(self):
        kit.initialize(self.project)
        view = self.project / kit.PROGRESS
        view.write_text(view.read_text() + "用户补充的内容\n")
        before = (self.project / kit.MANIFEST).read_bytes()
        with self.assertRaises(ValueError):
            kit.update_stage(self.project, "plan", "in_progress")
        self.assertIn("用户补充", view.read_text())
        self.assertEqual(before, (self.project / kit.MANIFEST).read_bytes())

    def test_old_registration_read_and_refresh_preserve_existing_states(self):
        kit.initialize(self.project, mode="execute")
        c = self.config()
        for key in ("round_scope", "scope_reason", "updated_at", "progress_history"):
            c.pop(key)
        for s in c["stages"].values():
            for key in ("completed", "remaining", "needs_from", "criteria"):
                s.pop(key)
        c["stages"]["S2"]["status"] = "in_progress"
        self.write_config(c)
        before = (self.project / kit.MANIFEST).read_bytes()
        kit.refresh_progress(self.project)
        self.assertEqual(before, (self.project / kit.MANIFEST).read_bytes())
        self.assertIn("旧登记未写本轮范围", (self.project / kit.PROGRESS).read_text())
        kit.set_scope(self.project, ["S2"], "当前用户仅要求提取材料")
        self.assertEqual(self.config()["stages"]["S2"]["status"], "in_progress")
        self.assertEqual(kit.workflow_position(self.config())[0], "S2")

    def test_invalid_scope_and_missing_evidence_do_not_propose_advancement(self):
        kit.initialize(self.project, mode="execute")
        for scope in (9, [], ["S1", "S1"], ["UNKNOWN"]):
            c = self.config()
            c["round_scope"] = scope
            self.write_config(c)
            r = subprocess.run([sys.executable, str(ROOT / "kit.py"), "status", str(self.project)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("暂不据此判断完成", r.stdout)
        c["round_scope"] = ["S1", "S2"]
        c["stages"]["S1"].update(status="done", completed="旧登记", evidence=["missing.md"])
        report = kit.render_progress(self.project, c)
        self.assertNotIn("当前：S2", report)
        self.assertIn("证据应定位", report)

    def test_status_is_read_only_and_cli_scope_progress_flow_works(self):
        kit.initialize(self.project, task="测试材料盘点")
        before = {p.name: p.read_bytes() for p in self.project.iterdir() if p.is_file()}
        cmd = [sys.executable, str(ROOT / "kit.py")]
        r = subprocess.run(cmd + ["status", str(self.project)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.project.iterdir() if p.is_file()})
        for args in (["set-scope", str(self.project), "S1", "--reason", "仅盘点材料"],
                     ["update-stage", str(self.project), "S1", "--state", "in_progress", "--remaining", "核对未读部分"],
                     ["progress", str(self.project)]):
            r = subprocess.run(cmd + args, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("本步剩余：核对未读部分", (self.project / kit.PROGRESS).read_text())


if __name__ == "__main__":
    unittest.main()
