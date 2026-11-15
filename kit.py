#!/usr/bin/env python3
"""Local scaffolding and structural checks. Does not call AI or judge business truth."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote

KIT = Path(__file__).resolve().parent
MANIFEST = "business-model-project.json"
STAGES = {
    "plan": "明确范围与实施方案", "S1": "材料盘点", "S2": "候选提取",
    "S3": "核查建模", "S4": "测试准备", "S5": "实际使用", "S6": "修订回归",
}
STATES = {"not_started": "未开始", "in_progress": "进行中", "blocked": "阻塞",
          "awaiting_review": "待核查／确认", "needs_recheck": "需复核",
          "done": "登记完成", "not_applicable": "不适用"}
PROGRESS = "工作进度.md"
PROGRESS_PREFIX = "<!-- business-modeling-kit-progress "
CRITERIA = {
    "plan": "本轮目标、范围、交付到哪、各步输入产物与完成标准有依据并记入实施方案。",
    "S1": "原件、实际阅读覆盖、支持的认识、关键缺口及其影响已列明。",
    "S2": "本轮材料已按实际覆盖提取，候选保留来源、说话人、条件和未知，并完成双向查漏。",
    "S3": "模型草稿、核查取舍、关键对象关系规则、依据、未知及版本清楚；采用状态有记录。",
    "S4": "本轮独立期望、原始依据、覆盖范围、不得断言内容和判定方法已固定版本。",
    "S5": "正确模型进入实际请求，有原始回答及逐项独立判读；未解决的失败不能算通过。",
    "S6": "修改理由、影响范围、新旧版本、回归结果和未覆盖部分清楚；无变更可说明不适用。",
}
STAGE_ACTIONS = {
    "plan": "明确本轮用途、范围和完成标准，形成实施方案与本轮步骤范围。",
    "S1": "盘点原件和实际阅读覆盖，登记已有依据、缺口及取得办法。",
    "S2": "提取有来源和条件的业务候选，核对完整问答并双向查漏。",
    "S3": "核查候选和取舍，组织模型草稿，记录依据、未知及采用状态。",
    "S4": "从原始依据准备独立测试期望、覆盖和判定方法，固定本轮版本。",
    "S5": "用当前模型实际运行约定任务，保存请求回答并按独立标准判读。",
    "S6": "按已定位的问题修订模型或方法，保留版本并验证受影响范围。",
}
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


def initialize(project, task="", materials=None, mode="plan", scope=None):
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
    for name in [MANIFEST, *FILES, "AI接续.md", "AGENTS.md", PROGRESS]:
        p = project / name
        if p.is_symlink() or (p.exists() and not p.is_file()):
            raise ValueError(f"目标不是普通文件，未初始化：{name}")
    existing = project / MANIFEST
    if existing.exists():
        load_project(project)  # Do not silently replace a damaged registration.
    project.mkdir(parents=True, exist_ok=True)
    config = {"schema_version": 1, "kit_path": str(KIT), "kit_version": version(),
              "mode": mode, "task": task, "materials": [str(materials)] if materials else [],
              "round_scope": scope if scope is not None else (["plan"] if mode == "plan" else list(STAGES)),
              "scope_reason": task or "按当前协作方式初始化，AI 须对照用户任务核实本轮范围。",
              "updated_at": timestamp(), "progress_history": [],
              "stages": {key: {"status": "not_started", "evidence": [], "note": "",
                               "completed": "", "remaining": "", "needs_from": "",
                               "criteria": CRITERIA[key]}
                         for key in STAGES}}
    scope_issues(config)
    save_new(existing, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    for name, source in FILES.items():
        save_new(project / name, (KIT / source).read_text(encoding="utf-8"))
    save_new(project / "AI接续.md", """# 本项目业务建模接续

先读 business-model-project.json，按其中 kit_path 找到工具包 AGENTS.md 和 08 学习路线。
再读本项目背景、实施方案、建模记录与资料索引；根据用户当前任务推进。
plan 仅准备方案，learn 解释并带学，execute 在已明确范围内执行；最新用户要求优先。
登记文件中的路径和状态由 AI 维护，原始资料与业务结论仍需独立核查。
没有实际证据不要标 done；不适用需写理由。模板存在不是步骤完成。
每次开工、接续和收活，先用 kit.py status 查看当前登记和实际证据，按 11 汇报当前节点、已完成、尚缺及流程下一步。
工作进度.md 是登记的可读视图，由 AI 更新登记后生成。下一步来自本轮范围内最早未完成步骤；额外建议另列。
若登记的工具包路径已失效，定位新位置并告知用户后修正登记，不改客户成果。
""")
    agents = project / "AGENTS.md"
    old = agents.read_text(encoding="utf-8") if agents.exists() else ""
    if MARKER not in old:
        with agents.open("a", encoding="utf-8") as f:
            f.write("\n" + MARKER + "\n## 业务建模任务入口\n"
                    "涉及业务建模时，先读本目录 AI接续.md 与 business-model-project.json。"
                    "保留本文件既有规则和用户当前要求。\n<!-- /business-modeling-kit -->\n")
    save_new(project / PROGRESS, managed_progress(project, load_project(project)))
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
    try:
        scope_issues(c)
    except ValueError as e:
        errors.append(str(e))
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
        for field in ("note", "completed", "remaining", "needs_from", "criteria"):
            if field in state and not isinstance(state[field], str):
                errors.append(f"{key} {field} 应为文字。")
        if state["status"] == "done" and "completed" in state and not str(state["completed"]).strip():
            errors.append(f"{key} 登记完成但未说明完成了什么。")
        if state["status"] == "done" and str(state.get("remaining", "")).strip():
            errors.append(f"{key} 仍有未完成项，不能登记完成。")
        if state["status"] in ("blocked", "not_applicable", "awaiting_review", "needs_recheck") and not str(state.get("note", "")).strip():
            errors.append(f"{key} 需要说明阻塞、等待、复核或不适用的理由。")
        for item in evidence:
            path = (project / item).resolve()
            if not inside(path, project) or not path.is_file():
                errors.append(f"{key} 证据应定位到项目内实际文件：{item}")
            elif state["status"] == "done" and path.suffix == ".md":
                body = path.read_text(encoding="utf-8")
                if "【填写】" in body or "【项目名称】" in body:
                    errors.append(f"{key} 完成证据仍有模板占位：{item}")
    return errors


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scope_issues(c):
    scope = c.get("round_scope")
    if scope is None:
        return  # Keep old registrations readable; report their fallback explicitly.
    if (not isinstance(scope, list) or not scope
            or any(not isinstance(k, str) or k not in STAGES for k in scope)
            or len(set(scope)) != len(scope)):
        raise ValueError("round_scope 应为不重复的本轮步骤列表，使用 plan、S1–S6；不能留空。")
    if not isinstance(c.get("scope_reason"), str) or not c["scope_reason"].strip():
        raise ValueError("本轮步骤范围需写明用户任务或实施方案依据 scope_reason。")


def round_scope(c):
    scope = c.get("round_scope")
    if scope is None:
        scope = ["plan"] if c.get("mode") == "plan" else list(STAGES)
    return [k for k in STAGES if k in scope]


def stage_record(c, key):
    stages = c.get("stages", {})
    state = stages.get(key, {}) if isinstance(stages, dict) else {}
    return state if isinstance(state, dict) else {}


def workflow_position(c):
    """Choose from recorded scope and fixed step order, never from generated advice."""
    pending = [k for k in round_scope(c)
               if stage_record(c, k).get("status") not in ("done", "not_applicable")]
    return (pending[0] if pending else None, pending[1] if len(pending) > 1 else None)


def render_progress(project, c):
    errors = project_issues(project, c)
    def cell(value):
        return str(value or "—").replace("|", "\\|").replace("\n", "<br>")
    lines = ["# 业务模型工作进度", "",
             f"任务：{c.get('task') or '待从项目背景核实'}",
             f"更新时间：{c.get('updated_at') or '旧记录未登记'}；登记工具包版本：{c.get('kit_version')}",
             "", "状态由 AI 据实际记录维护；文件存在不等于内容正确或客户验收。"]
    if "round_scope" not in c:
        lines += ["旧登记未写本轮范围：暂按 mode 展示，AI 需对照用户任务核实，不能凭此扩大工作。"]
    scope = round_scope(c) if not any("round_scope" in e for e in errors) else []
    lines += [f"本轮步骤：{' → '.join(scope) or '范围待修正'}；依据：{c.get('scope_reason') or '旧登记未记录'}", "",
              "| 步骤 | 本轮 | 状态 | 已完成什么 | 尚缺／需谁提供 | 成果与依据 |",
              "| --- | --- | --- | --- | --- | --- |"]
    for key, label in STAGES.items():
        s = stage_record(c, key)
        status = s.get("status")
        display = STATES.get(status, "状态无效") if isinstance(status, str) else "状态无效"
        ev = s.get("evidence", [])
        ev = "、".join(ev) if isinstance(ev, list) and all(isinstance(p, str) for p in ev) else "证据格式待修正"
        remaining = "；".join(str(s.get(k) or "") for k in ("remaining", "needs_from", "note") if s.get(k))
        lines.append("| " + " | ".join(map(cell, [f"{key} {label}", "是" if key in scope else "范围外",
                                                      display, s.get("completed"), remaining, ev])) + " |")
    lines += ["", "## 当前节点与流程下一步", ""]
    if errors:
        lines += ["登记有问题，暂不据此判断完成或推进步骤。先核对登记与实际证据：", *[f"- {e}" for e in errors]]
        return "\n".join(lines) + "\n"
    applicable = [k for k in scope if stage_record(c, k).get("status") != "not_applicable"]
    done = sum(stage_record(c, k).get("status") == "done" for k in applicable)
    lines += [f"本轮登记完成 {done}/{len(applicable)} 个适用步骤；不换算工时或业务完成百分比。"]
    current, following = workflow_position(c)
    if current is None:
        lines += ["当前：本轮范围内步骤已登记完成或有理由不适用。",
                  "流程下一步：本轮收尾与接续；范围外步骤尚未因此完成，不自动进入指标库或其他工作。"]
    else:
        state = stage_record(c, current)
        lines += [f"当前：{current} {STAGES[current]} · {STATES[state['status']]}",
                  f"本步完成标准：{state.get('criteria') or CRITERIA[current]}",
                  f"流程下一步：仍在 {current}，{STAGE_ACTIONS[current]}"]
        if state["status"] in ("awaiting_review", "blocked", "needs_recheck"):
            lines += [f"先解决：{state.get('remaining') or state.get('note')}；需谁处理：{state.get('needs_from') or 'AI 据实际依赖定位，未说明'}。不能跳过此项宣布推进。"]
        elif state.get("remaining"):
            lines += [f"本步剩余：{state['remaining']}"]
        if following:
            lines += [f"达到本步标准后，后续未完成节点：{following} {STAGES[following]}；目前未自动进入。"]
        else:
            lines += ["达到本步标准后，本轮收尾；后续范围另按用户已明确的任务接续。"]
    lines += ["", "额外建议不参与节点选择；有并行工作或回退时，AI 在本轮简报说明范围与依据。"]
    return "\n".join(lines) + "\n"


def managed_progress(project, c):
    body = render_progress(project, c)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"{PROGRESS_PREFIX}sha256={digest} -->\n" + body


def check_progress_target(project):
    path = project / PROGRESS
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("工作进度位置不是普通文件，保留原状。")
    if path.exists():
        header, sep, body = path.read_text(encoding="utf-8").partition("\n")
        expected = f"{PROGRESS_PREFIX}sha256={hashlib.sha256(body.encode('utf-8')).hexdigest()} -->"
        if not sep or header != expected:
            raise ValueError("工作进度.md 是已有手写文件或已被修改；先保留并合并到登记，再另存旧版，不自动覆盖。")


def atomic_write(path, content):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"目标不是普通文件，保留原状：{path.name}")
    # Use an exclusive temporary file next to the destination for atomic replacement.
    import tempfile
    fd, temp = tempfile.mkstemp(prefix=".bm-progress-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def refresh_progress(project):
    c = load_project(project)
    check_progress_target(project)
    atomic_write(project / PROGRESS, managed_progress(project, c))


def save_progress_change(project, new, change):
    errors = project_issues(project, new)
    if errors:
        raise ValueError("；".join(errors))
    check_progress_target(project)
    history = new.setdefault("progress_history", [])
    if not isinstance(history, list):
        raise ValueError("progress_history 应为历史列表，保留原件后修正。")
    now = timestamp()
    new["updated_at"] = now
    history.append({"at": now, **change})
    atomic_write(project / MANIFEST, json.dumps(new, ensure_ascii=False, indent=2) + "\n")
    atomic_write(project / PROGRESS, managed_progress(project, new))


def update_stage(project, key, status, **fields):
    old = load_project(project)
    scope_issues(old)
    if key not in round_scope(old):
        raise ValueError("此步骤不在本轮范围；先按用户任务核对范围，不能自动扩展。")
    new = json.loads(json.dumps(old))
    state = stage_record(new, key)
    if not state:
        raise ValueError("原阶段登记缺失或无效，保留原件并修正。")
    before = dict(state)
    state.update({k: v for k, v in fields.items() if v is not None})
    state["status"] = status
    if status == "done" and not str(state.get("completed", "")).strip():
        raise ValueError("登记完成需说明已完成什么，并提供实际证据。")
    reopened = {}
    changed_basis = any(before.get(f) != state.get(f) for f in ("criteria", "evidence", "completed"))
    if before.get("status") == "done" and (status != "done" or changed_basis):
        after = False
        for downstream in STAGES:
            if downstream == key:
                after = True
                continue
            s = stage_record(new, downstream)
            if after and s.get("status") in ("done", "not_applicable"):
                reopened[downstream] = dict(s)
                s.update(status="needs_recheck", note=f"{key} 已回退或完成依据变更，先核实本步是否受影响；原状态及证据保留，尚未判失败。")
    save_progress_change(project, new, {"kind": "stage", "stage": key, "before": before,
                                           "after": dict(state), "downstream_before_recheck": reopened})


def set_scope(project, scope, reason):
    old = load_project(project)
    new = json.loads(json.dumps(old))
    new.update(round_scope=scope, scope_reason=reason)
    save_progress_change(project, new, {"kind": "scope", "before": old.get("round_scope"),
                                           "after": scope, "reason": reason})


def package_issues(root):
    errors = []
    required = ["AGENTS.md", "START-HERE.md", "VERSION", "08-实施方案与学习路线.md",
                "11-工作进度与接续.md", "templates/工作进度.md",
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
    start.add_argument("--scope", nargs="+", choices=list(STAGES), help="本轮已明确要执行的步骤")
    status = sub.add_parser("status", help="查看登记状态和证据路径问题")
    status.add_argument("project", type=Path)
    progress = sub.add_parser("progress", help="从登记刷新可读工作进度，不改变状态")
    progress.add_argument("project", type=Path)
    update = sub.add_parser("update-stage", help="据证据更新一个步骤并刷新工作进度")
    update.add_argument("project", type=Path)
    update.add_argument("stage", choices=list(STAGES))
    update.add_argument("--state", choices=list(STATES), required=True)
    for field in ("completed", "remaining", "needs-from", "note", "criteria"):
        update.add_argument("--" + field)
    update.add_argument("--evidence", nargs="*", help="该步当前证据列表；旧列表留历史，传空可清空")
    scope = sub.add_parser("set-scope", help="按用户任务设置本轮步骤范围，保留历史")
    scope.add_argument("project", type=Path)
    scope.add_argument("stages", nargs="+", choices=list(STAGES))
    scope.add_argument("--reason", required=True)
    check = sub.add_parser("check", help="检查工具包及可选项目的结构")
    check.add_argument("--project", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            p = initialize(args.project, args.task, args.materials, args.mode, args.scope)
            print(f"项目已准备：{p}\n已有文件与登记保留；本次没有执行业务建模。\n下一步：读取 AI接续.md 与工作进度.md，按本轮实际任务接续。")
            return 0
        if args.command in ("progress", "update-stage", "set-scope"):
            p = args.project.expanduser().resolve()
            if args.command == "progress":
                refresh_progress(p)
            elif args.command == "set-scope":
                set_scope(p, args.stages, args.reason)
            else:
                update_stage(p, args.stage, args.state, **{field: getattr(args, field)
                             for field in ("completed", "remaining", "needs_from", "note", "criteria", "evidence")})
            c = load_project(p)
            print(render_progress(p, c))
            return 1 if project_issues(p, c) else 0
        if args.command == "status":
            p = args.project.expanduser().resolve()
            c = load_project(p)
            errors = project_issues(p, c)
            print(render_progress(p, c))
            return 1 if errors else 0
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
