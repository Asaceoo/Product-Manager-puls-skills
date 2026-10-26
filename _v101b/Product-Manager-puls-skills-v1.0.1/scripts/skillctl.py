#!/usr/bin/env python3
"""技能库运维工具（本分发版实现）。

上游 ``scripts/`` 目录未随技能一同分发，但 ``pm-skill-creator`` 与
``skill-authoring-workflow`` 两个元技能会指导用户执行其中的命令。本文件补齐这些能力，
使文档里的每条命令都能真实运行。

入口薄壳见同目录的 ``*.sh`` / ``*.py``，它们只做参数转发。

子命令
------
    find      --keyword <词>                        搜索技能
    metadata  <SKILL.md>                            校验 frontmatter
    triggers  <SKILL.md> [--show-cases]             检查触发语与场景
    add       <source.md> [--name N]                从文档生成技能骨架
    build     --name N [--type T] [--theme M]       参数式骨架生成
    test      [--skill N] [--smoke]                 跑审查与校验
    zip       [--skill N|--type T|--preset P]       打包
    validate                                        清单约束校验
    dist                                            完整打包流水线
    catalog                                         重建 catalog 索引
    freshness                                       检查 dist 是否过期
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
TOOLS = ROOT / "tools"
CATALOG = ROOT / "catalog"
DIST = ROOT / "dist"
CST = timezone(timedelta(hours=8))

KNOWN_TYPES = ("workflow", "component", "interactive")
KNOWN_THEMES = (
    "market-intelligence", "pm-artifacts", "finance-metrics", "discovery-research",
    "eol-transition", "career-leadership", "workshops-facilitation", "validation-experiments",
    "strategy-positioning", "stakeholder-comms", "ai-agents", "product-lifecycle", "meta-authoring",
)


# --------------------------------------------------------------------------- #
# 公共工具
# --------------------------------------------------------------------------- #
def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def frontmatter(text: str) -> Dict[str, str]:
    """解析顶层标量字段。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: Dict[str, str] = {}
    for raw in parts[1].splitlines():
        if not raw.strip() or raw.startswith((" ", "\t", "#")) or ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        data[key.strip()] = value.strip().strip("\"'")
    return data


def all_skill_dirs() -> List[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


def run_tool(name: str, *args: str) -> Tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(TOOLS / name), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


# --------------------------------------------------------------------------- #
# find
# --------------------------------------------------------------------------- #
def cmd_find(args) -> int:
    keyword = args.keyword.lower()
    hits: List[Tuple[str, str, int]] = []
    for d in all_skill_dirs():
        text = read(d / "SKILL.md")
        name = d.name
        fm = frontmatter(text)
        in_name = keyword in name
        in_desc = keyword in fm.get("description", "").lower()
        body_hits = len(re.findall(re.escape(keyword), text.lower()))
        if in_name or in_desc or body_hits:
            hits.append((name, fm.get("description", ""), body_hits))

    if not hits:
        print(f"没有技能匹配 {args.keyword!r}。")
        return 1

    hits.sort(key=lambda x: (-x[2], x[0]))
    print(f"匹配 {len(hits)} 个技能（按正文命中次数排序）：\n")
    for name, desc, count in hits:
        print(f"  {name:<34} 命中 {count:>3}    {desc[:70]}")
    print("\n新建技能前先看这张表：语义重叠意味着该扩展已有技能，而不是再造一个。")
    return 0


# --------------------------------------------------------------------------- #
# metadata
# --------------------------------------------------------------------------- #
def cmd_metadata(args) -> int:
    target = Path(args.path)
    if not target.exists():
        return fail(f"文件不存在：{target}")
    text = read(target)
    fm = frontmatter(text)
    problems: List[str] = []

    if not fm:
        problems.append("缺少或损坏的 frontmatter（需以 --- 开头并闭合）")
    else:
        for key in ("name", "description", "type", "theme"):
            if not fm.get(key):
                problems.append(f"缺少必填字段 {key}")
        if fm.get("name") and fm["name"] != target.parent.name:
            problems.append(f"name={fm['name']!r} 与目录名 {target.parent.name!r} 不一致")
        if fm.get("type") and fm["type"] not in KNOWN_TYPES:
            problems.append(f"type={fm['type']!r} 不在 {KNOWN_TYPES}")
        if fm.get("theme") and fm["theme"] not in KNOWN_THEMES:
            problems.append(f"theme={fm['theme']!r} 不是已知主题")
        desc = fm.get("description", "")
        if desc and len(desc) < 40:
            problems.append(f"description 仅 {len(desc)} 字符，太短")

    if problems:
        print(f"FAIL {target}")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"PASS {target}")
    return 0


# --------------------------------------------------------------------------- #
# triggers
# --------------------------------------------------------------------------- #
def cmd_triggers(args) -> int:
    target = Path(args.path)
    if not target.exists():
        return fail(f"文件不存在：{target}")
    text = read(target)
    fm = frontmatter(text)
    desc = fm.get("description", "")

    checks = [
        ("触发语（Use when/for/to）", bool(re.search(r"\b[Uu]se (?:when|for|to|this|it)\b", desc))),
        ("argument-hint 字段", bool(fm.get("argument-hint"))),
        ("description 长度 40–400", 40 <= len(desc) <= 400),
        ("scenarios 示例语句", "scenarios:" in text),
        ("输入要求声明", bool(re.search(r"^##\s+Input|Arriving empty-handed|no input needed", text, re.MULTILINE))),
        ("产出章节", bool(re.search(r"^##\s+(?:Output|Deliverable|Application|Workflow|Process)", text, re.MULTILINE))),
    ]

    failed = 0
    print(f"触发就绪度：{target.parent.name}\n")
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failed += 1

    if args.show_cases:
        # scenarios 写在 frontmatter 里，必须从 frontmatter 取，不能从正文扫
        block = text.split("---", 2)[1] if text.startswith("---") else ""
        cases: List[str] = []
        in_scenarios = False
        for raw in block.splitlines():
            if re.match(r"^scenarios:\s*$", raw):
                in_scenarios = True
                continue
            if in_scenarios:
                if re.match(r"^[A-Za-z0-9_-]+:", raw):  # 下一个顶层字段，结束
                    break
                item = re.match(r'^\s*-\s*"?(.+?)"?\s*$', raw)
                if item:
                    cases.append(item.group(1))
        if cases:
            print("\n  已记录的调用场景：")
            for c in cases:
                print(f"    - {c}")
        else:
            print("\n  未找到 scenarios 场景语句（建议补 2–3 条真实调用语）。")

    print()
    print("通过" if failed == 0 else f"{failed} 项未通过")
    return 0 if failed == 0 else 1


# --------------------------------------------------------------------------- #
# add / build
# --------------------------------------------------------------------------- #
SKILL_TEMPLATE = """---
name: {name}
argument-hint: "[what the user should bring]"
description: {description}
type: {type}
theme: {theme}
---

## Purpose

{intent}

## Input

**Works best with:** {works_best_with}
**Also useful:** {also_useful}

Arriving empty-handed works too — the workflow collects what it needs one question at a time.

**Example invocation:** `{example}`

## Key Concepts

{key_concepts}

## Application

{application}

## Examples

See `template.md` for the fill-in structure.

## Common Pitfalls

**Pitfall 1: {pitfall_title}**
**Symptom:** {pitfall_symptom}

**Fix:** {pitfall_fix}

## References

### Related Skills

- (list skills this one hands off to)

### Provenance

{provenance}
"""


def _slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug or "new-skill"


def _scaffold(name: str, description: str, skill_type: str, theme: str, intent: str, provenance: str) -> int:
    target = SKILLS / name
    if target.exists():
        return fail(f"技能目录已存在：{target}")

    body = SKILL_TEMPLATE.format(
        name=name,
        description=description,
        type=skill_type,
        theme=theme,
        intent=intent,
        works_best_with="(the decision the user is facing)",
        also_useful="(any research, data, or prior documents they have)",
        example=f"Use {name}: <the user's situation in one line>",
        key_concepts="(define the 3–5 concepts this skill depends on)",
        application="(describe the step-by-step sequence, with numbered options at decision points)",
        pitfall_title="(the most common way this goes wrong)",
        pitfall_symptom="(what you see when it happens)",
        pitfall_fix="(the correction)",
        provenance=provenance,
    )
    write(target / "SKILL.md", body)
    write(
        target / "template.md",
        f"# {name} — fill-in template\n\n"
        "## Section 1\n\n(Instructions for this section)\n\n"
        "## Section 2\n\n(Instructions for this section)\n",
    )
    print(f"已创建 {target.relative_to(ROOT).as_posix()}/")
    print("  下一步：")
    print("    1. 补完 SKILL.md 的正文（把括号里的占位换成本领域内容）")
    print("    2. python tools/manifest.py generate")
    print("    3. python tools/audit.py")
    return 0


def cmd_add(args) -> int:
    source = Path(args.source)
    if not source.exists() and not args.force:
        return fail(f"源文件不存在：{source}（确认后可用 --force 忽略）")

    name = args.name or _slug(source.stem)
    excerpt = ""
    if source.exists():
        excerpt = " ".join(read(source).split())[:300]

    description = (
        args.description
        or f"Turn source material into a structured {args.type} for product decisions. "
        f"Use when the user brings notes from {name.replace('-', ' ')} and needs a reviewable output."
    )
    provenance = (
        f"- Scaffolded from `{source.as_posix()}` on "
        f"{datetime.now(CST).strftime('%Y-%m-%d')} via `scripts/add-a-skill.sh`."
    )
    intent = excerpt or "(summarize what this skill helps the user decide)"
    return _scaffold(name, description, args.type, args.theme, intent, provenance)


def cmd_build(args) -> int:
    name = _slug(args.name)
    description = (
        args.description
        or f"Run {name.replace('-', ' ')} as a structured workflow. "
        "Use when the user needs a repeatable sequence rather than a one-off answer."
    )
    provenance = f"- Authored on {datetime.now(CST).strftime('%Y-%m-%d')} via `scripts/build-a-skill.sh`."
    return _scaffold(name, description, args.type, args.theme, "(state the intent in one paragraph)", provenance)


# --------------------------------------------------------------------------- #
# test / validate / dist / freshness
# --------------------------------------------------------------------------- #
def cmd_test(args) -> int:
    if args.skill:
        target = SKILLS / args.skill
        if not target.is_dir():
            return fail(f"技能不存在：{args.skill}")
        print(f"== 单技能检查：{args.skill} ==")
        metadata_code = cmd_metadata(argparse.Namespace(path=str(target / "SKILL.md")))
        print()
        trigger_code = cmd_triggers(argparse.Namespace(path=str(target / "SKILL.md"), show_cases=True))
        if metadata_code or trigger_code:
            return 1
        print("\n单技能检查通过。")
        return 0

    print("== 全量审查 ==")
    code, out = run_tool("audit.py", *(["--strict"] if args.smoke else []))
    summary = [l for l in out.splitlines() if l.startswith("结果：")]
    print(f"  {summary[0] if summary else out.strip()[:120]}")

    print("== 清单校验 ==")
    vcode, vout = run_tool("validate.py")
    vsum = [l for l in vout.splitlines() if l.startswith("校验结果")]
    print(f"  {vsum[0] if vsum else vout.strip()[:120]}")

    return 0 if (code == 0 and vcode == 0) else 1


def cmd_zip(args) -> int:
    targets: List[Path] = []
    if args.skill:
        target = SKILLS / args.skill
        if not target.is_dir():
            return fail(f"技能不存在：{args.skill}")
        targets = [target]
    elif args.type:
        targets = [d for d in all_skill_dirs() if frontmatter(read(d / "SKILL.md")).get("type") == args.type]
        if not targets:
            return fail(f"没有 type={args.type} 的技能")
    elif args.preset:
        presets = {
            "core-pm": ["prd-development", "user-story", "problem-statement", "prioritization-advisor", "roadmap-planning"],
            "discovery": ["discovery-process", "discovery-interview-prep", "jobs-to-be-done", "opportunity-solution-tree", "proto-persona"],
            "market": ["swot-analysis", "porters-five-forces", "pestel-analysis", "market-landscape-scan", "competitive-research-snapshot"],
            "meta": ["pm-skill-creator", "skill-authoring-workflow"],
        }
        names = presets.get(args.preset)
        if not names:
            return fail(f"未知 preset：{args.preset}（可选 {', '.join(presets)}）")
        targets = [SKILLS / n for n in names if (SKILLS / n).is_dir()]
    else:
        return fail("需要 --skill、--type 或 --preset 之一")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    for target in targets:
        zip_path = out_dir / f"{target.name}-v{version}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for item in sorted(target.rglob("*")):
                if item.is_file() and "__pycache__" not in item.parts:
                    zf.write(item, f"{target.name}/{item.relative_to(target).as_posix()}")
        print(f"  {zip_path}  {zip_path.stat().st_size / 1024:.1f} KB")

    print(f"\n已打包 {len(targets)} 个技能 → {out_dir}")
    return 0


def cmd_validate(args) -> int:
    code, out = run_tool("validate.py")
    print(out.strip())
    return code


def cmd_dist(args) -> int:
    code, out = run_tool("build.py", *args.extra)
    print(out.strip())
    return code


def cmd_freshness(args) -> int:
    """dist 中的包是否落后于源码。"""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    expectations = [DIST / f"Product-Manager-puls-skills-v{version}.zip"]
    missing = [p.name for p in expectations if not p.exists()]
    if missing:
        print(f"dist 缺少当前版本的包：{', '.join(missing)}")
        print("运行 `./scripts/build-dist.sh` 重新打包。")
        return 1

    newest_src = max(
        (p.stat().st_mtime for p in SKILLS.rglob("*") if p.is_file()), default=0
    )
    zip_mtime = expectations[0].stat().st_mtime
    if newest_src > zip_mtime:
        lag = int(newest_src - zip_mtime)
        print(f"dist 已过期：源码比包新 {lag} 秒，请重新打包。")
        return 1

    print(f"dist 与源码同步（v{version}）。")
    return 0


# --------------------------------------------------------------------------- #
# catalog
# --------------------------------------------------------------------------- #
def cmd_catalog(args) -> int:
    entries = []
    for d in all_skill_dirs():
        fm = frontmatter(read(d / "SKILL.md"))
        entries.append(
            {
                "name": d.name,
                "type": fm.get("type", ""),
                "theme": fm.get("theme", ""),
                "description": fm.get("description", ""),
            }
        )

    by_theme: Dict[str, List[Dict[str, str]]] = {}
    for e in entries:
        by_theme.setdefault(e["theme"] or "(none)", []).append(e)

    lines = ["# Skills by theme", "", f"生成时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M')}", ""]
    for theme in sorted(by_theme, key=lambda t: (-len(by_theme[t]), t)):
        lines.append(f"## {theme}（{len(by_theme[theme])}）")
        lines.append("")
        lines.append("| 技能 | 类型 | 作用 |")
        lines.append("|---|---|---|")
        for e in sorted(by_theme[theme], key=lambda x: x["name"]):
            desc = e["description"].split(".")[0][:90]
            lines.append(f"| `{e['name']}` | {e['type']} | {desc} |")
        lines.append("")

    write(CATALOG / "skills-by-theme.md", "\n".join(lines))
    print(f"已生成 {(CATALOG / 'skills-by-theme.md').relative_to(ROOT).as_posix()}（{len(entries)} 个技能）")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(prog="skillctl", description="技能库运维工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="搜索技能")
    p.add_argument("--keyword", required=True)
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("metadata", help="校验 frontmatter")
    p.add_argument("path")
    p.set_defaults(func=cmd_metadata)

    p = sub.add_parser("triggers", help="检查触发语")
    p.add_argument("path")
    p.add_argument("--show-cases", action="store_true")
    p.set_defaults(func=cmd_triggers)

    p = sub.add_parser("add", help="从文档生成技能骨架")
    p.add_argument("source")
    p.add_argument("--name")
    p.add_argument("--type", default="workflow", choices=KNOWN_TYPES)
    p.add_argument("--theme", default="pm-artifacts", choices=KNOWN_THEMES)
    p.add_argument("--description")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("build", help="参数式生成技能骨架")
    p.add_argument("--name", required=True)
    p.add_argument("--type", default="workflow", choices=KNOWN_TYPES)
    p.add_argument("--theme", default="pm-artifacts", choices=KNOWN_THEMES)
    p.add_argument("--description")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("test", help="跑审查与校验")
    p.add_argument("--skill")
    p.add_argument("--smoke", action="store_true")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("zip", help="打包技能")
    p.add_argument("--skill")
    p.add_argument("--type")
    p.add_argument("--preset")
    p.add_argument("--output", default=str(DIST / "skill-zips"))
    p.set_defaults(func=cmd_zip)

    sub.add_parser("validate", help="清单约束校验").set_defaults(func=cmd_validate)
    sub.add_parser("catalog", help="重建 catalog 索引").set_defaults(func=cmd_catalog)
    sub.add_parser("freshness", help="检查 dist 是否过期").set_defaults(func=cmd_freshness)

    p = sub.add_parser("dist", help="完整打包流水线")
    p.add_argument("extra", nargs="*", help="透传给 tools/build.py 的参数")
    p.set_defaults(func=cmd_dist)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
