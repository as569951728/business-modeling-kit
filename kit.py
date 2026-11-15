#!/usr/bin/env python3
"""Local scaffolding and structural checks. Does not call AI or judge business truth."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

KIT = Path(__file__).resolve().parent
MANIFEST = "business-model-project.json"
STAGES = {
    "plan": "实施方案", "S1": "材料盘点", "S2": "候选提取",
    "S3": "核查建模", "S4": "测试准备", "S5": "实际使用", "S6": "修订回归",
}
STATES = {"not_started": "未开始", "in_progress": "进行中", "blocked": "阻塞",
          "done": "登记完成", "not_applicable": "不适用"}
FILES = {"项目背景.md": "templates/项目背景.md", "实施方案.md": "templates/实施方案.md",
         "建模记录.md": "templates/建模记录.md"}
MARKER = "<!-- business-modeling-kit -->"


def version():
    path = KIT / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else "unknown"


def save_new(path, content):
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"目标不是普通文件，保留原状：{path.name}")
        return False
    with path.open("x", encoding="utf-8") as f:
        f.write(content)
    return True


def inside(path, root):
    return path == root or root in path.parents


def initialize(project, task="", materials=None, mode="plan"):
    if version() == "unknown":
        raise ValueError("工具包缺少 VERSION，请先修复工具包，再登记客户项目。")
    project = project.expanduser().resolve()
    if inside(project, KIT):
        raise ValueError("请把客户项目放到工具包目录之外，通用方法与客户材料分开。")
    if materials is not None:
        materials = materials.expanduser().resolve()
        if not materials.exists():
            raise ValueError(f"资料位置不存在：{materials}。尚无资料时可不传 --materials。")
    if project.exists() and not project.is_dir():
        raise ValueError("客户项目位置必须是目录。")
    # Reject unsafe targets before creating or appending any managed file.
    for name in [MANIFEST, *FILES, "AI接续.md", "AGENTS.md"]:
        p = project / name
        if p.is_symlink() or (p.exists() and not p.is_file()):
            raise ValueError(f"目标不是普通文件，未初始化：{name}")
    existing = project / MANIFEST
    if existing.exists():
        load_project(project)  # Do not silently replace a damaged registration.
    project.mkdir(parents=True, exist_ok=True)
    config = {"schema_version": 1, "kit_path": str(KIT), "kit_version": version(),
              "mode": mode, "task": task, "materials": [str(materials)] if materials else [],
              "stages": {key: {"status": "not_started", "evidence": [], "note": ""}
                         for key in STAGES}}
    save_new(existing, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    for name, source in FILES.items():
        save_new(project / name, (KIT / source).read_text(encoding="utf-8"))
    save_new(project / "AI接续.md", """# 本项目业务建模接续

先读 business-model-project.json，按其中 kit_path 找到工具包 AGENTS.md 和 08 学习路线。
再读本项目背景、实施方案、建模记录与资料索引；根据用户当前任务推进。
plan 仅准备方案，learn 解释并带学，execute 在已明确范围内执行；最新用户要求优先。
登记文件中的路径和状态由 AI 维护，原始资料与业务结论仍需独立核查。
没有实际证据不要标 done；不适用需写理由。模板存在不是步骤完成。
若登记的工具包路径已失效，定位新位置并告知用户后修正登记，不改客户成果。
""")
    agents = project / "AGENTS.md"
    old = agents.read_text(encoding="utf-8") if agents.exists() else ""
    if MARKER not in old:
        with agents.open("a", encoding="utf-8") as f:
            f.write("\n" + MARKER + "\n## 业务建模任务入口\n"
                    "涉及业务建模时，先读本目录 AI接续.md 与 business-model-project.json。"
                    "保留本文件既有规则和用户当前要求。\n<!-- /business-modeling-kit -->\n")
    return project


def load_project(project):
    p = project / MANIFEST
    if not p.is_file():
        raise ValueError("未找到项目登记；先使用 init，或按 05 文档手工接续现有项目。")
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as e:
        raise ValueError("项目登记不是有效 JSON，保留原件并修正后再继续。") from e
    if not isinstance(c, dict) or c.get("schema_version") != 1:
        raise ValueError("项目登记版本无法识别，不自动覆盖。")
    return c


def project_issues(project, c):
    project = project.expanduser().resolve()
    errors = []
    kit_path = c.get("kit_path")
    if not isinstance(kit_path, str) or not kit_path.strip() or not (Path(kit_path) / "AGENTS.md").is_file():
        errors.append("登记的工具包位置失效，请定位实际工具包后修正 kit_path。")
    elif not (Path(kit_path) / "VERSION").is_file():
        errors.append("登记的工具包缺少 VERSION。")
    if c.get("mode") not in ("plan", "learn", "execute"):
        errors.append("mode 应为 plan、learn 或 execute。")
    materials = c.get("materials")
    if not isinstance(materials, list) or any(not isinstance(p, str) for p in materials):
        errors.append("materials 应为路径列表。")
    else:
        for p in materials:
            target = Path(p).expanduser()
            if not target.is_absolute():
                target = project / target
            if not target.exists():
                errors.append(f"资料位置已失效：{p}")
    for name in [*FILES, "AI接续.md", "AGENTS.md"]:
        if not (project / name).is_file():
            errors.append(f"接续文件缺失：{name}")
    stages = c.get("stages", {})
    if not isinstance(stages, dict):
        return errors + ["stages 应为阶段记录。"]
    for key in STAGES:
        state = stages.get(key)
        if not isinstance(state, dict) or not isinstance(state.get("status"), str) or state.get("status") not in STATES:
            errors.append(f"{key} 缺少合法状态。")
            continue
        evidence = state.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(p, str) for p in evidence):
            errors.append(f"{key} evidence 应为项目内文件路径列表。")
            continue
        if state["status"] == "done" and not evidence:
            errors.append(f"{key} 登记完成但没有证据路径。")
        if state["status"] in ("blocked", "not_applicable") and not str(state.get("note", "")).strip():
            errors.append(f"{key} 需要说明阻塞或不适用的理由。")
        for item in evidence:
            path = (project / item).resolve()
            if not inside(path, project) or not path.is_file():
                errors.append(f"{key} 证据应定位到项目内实际文件：{item}")
            elif state["status"] == "done" and path.suffix == ".md":
                body = path.read_text(encoding="utf-8")
                if "【填写】" in body or "【项目名称】" in body:
                    errors.append(f"{key} 完成证据仍有模板占位：{item}")
    return errors


def package_issues(root):
    errors = []
    required = ["AGENTS.md", "START-HERE.md", "VERSION", "08-实施方案与学习路线.md",
                "templates/实施方案.md", "assets/客户现场Checkpoint.pdf", *FILES.values()]
    for name in required:
        if not (root / name).is_file():
            errors.append(f"包内文件缺失：{name}")
    for p in sorted(root.rglob("*.md")):
        if any(part in (".git", "tmp", "output", "__pycache__") for part in p.relative_to(root).parts):
            continue
        body = p.read_text(encoding="utf-8")
        if body.count("```") % 2:
            errors.append(f"代码块未闭合：{p.relative_to(root)}")
        for href in re.findall(r"\]\(([^)]+)\)", body):
            if href.startswith(("https://", "http://", "#")):
                continue
            target = (p.parent / unquote(href.split("#", 1)[0])).resolve()
            if not inside(target, root.resolve()) or not target.exists():
                errors.append(f"无效或包外文件引用：{p.relative_to(root)} -> {href}")
    return errors


def main():
    parser = argparse.ArgumentParser(description="业务建模工具包：登记、接续和结构检查；不调用 AI。")
    parser.add_argument("--version", action="version", version=version())
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("init", help="准备客户项目，保留已有文件")
    start.add_argument("project", type=Path)
    start.add_argument("--task", default="")
    start.add_argument("--materials", type=Path)
    start.add_argument("--mode", choices=["plan", "learn", "execute"], default="plan")
    status = sub.add_parser("status", help="查看登记状态和证据路径问题")
    status.add_argument("project", type=Path)
    check = sub.add_parser("check", help="检查工具包及可选项目的结构")
    check.add_argument("--project", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            p = initialize(args.project, args.task, args.materials, args.mode)
            print(f"项目已准备：{p}\n已有文件与登记保留；本次没有执行业务建模。\n下一步：让 AI 读 AI接续.md，先形成项目背景和实施方案。")
            return 0
        if args.command == "status":
            p = args.project.expanduser().resolve()
            c = load_project(p)
            errors = project_issues(p, c)
            print(f"任务：{c.get('task') or '待从项目背景核实'}\n模式：{c.get('mode')}；工具包登记版本：{c.get('kit_version')}")
            print("以下为登记状态，证据存在不代表业务验收通过：")
            stages = c.get("stages", {})
            for key, label in STAGES.items():
                state = stages.get(key, {}) if isinstance(stages, dict) else {}
                state = state if isinstance(state, dict) else {}
                value = state.get('status')
                label_value = STATES.get(value, '状态无效') if isinstance(value, str) else '状态无效'
                print(f"{key} {label}：{label_value}")
            print("下一步：先处理下列问题。" if errors else "下一步：结合实施方案与建模记录，继续本轮尚未完成的任务。")
        else:
            errors = package_issues(KIT)
            if args.project:
                p = args.project.expanduser().resolve()
                errors += project_issues(p, load_project(p))
            if not errors:
                print("结构检查通过。未自动判定业务含义、采用状态或 Agent 效果。")
        for error in errors:
            print(f"- {error}")
        return 1 if errors else 0
    except (OSError, ValueError) as e:
        print(f"无法继续：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
