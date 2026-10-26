#!/usr/bin/env python3
"""清单约束校验器 —— 打包前的最后一道闸门。

与 ``audit.py`` 的分工
----------------------
``audit.py`` 看**内容质量**（写得好不好、能不能被 Agent 用）。
``validate.py`` 看**交付一致性**（清单与磁盘是否同一份东西、版本是否对齐、缺没缺文件）。

两者都通过，才允许打包。

CLI
---
    python tools/validate.py            # 全量校验，失败退出码 1
    python tools/validate.py --warn-as-error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manifest as manifest_mod  # noqa: E402
import version as version_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PATHS: Sequence[str] = (
    "README.md",
    "AGENTS.md",
    "VERSION",
    "versions.json",
    "LICENSE",
    "NOTICE",
    "MANIFEST.json",
    "docs/USER-MANUAL.md",
    "docs/TECH-MANUAL.md",
    "tools/version.py",
    "tools/manifest.py",
    "tools/audit.py",
    "tools/build.py",
    "tools/validate.py",
    "tools/install.py",
)

#: 技能内容总字节上限（超过说明混入了构建产物或大二进制）
MAX_SKILLS_BYTES = 8 * 1024 * 1024


@dataclass
class Result:
    level: str  # PASS / WARN / FAIL
    code: str
    message: str


def check_required_paths() -> List[Result]:
    out: List[Result] = []
    for rel in REQUIRED_PATHS:
        path = ROOT / rel
        if not path.exists():
            out.append(Result("FAIL", "L1", f"缺少必需文件：{rel}"))
        elif path.is_file() and path.stat().st_size == 0:
            out.append(Result("FAIL", "L1", f"必需文件为空：{rel}"))
    if not out:
        out.append(Result("PASS", "L1", f"必需文件齐备（{len(REQUIRED_PATHS)} 项）"))
    return out


def check_manifest() -> List[Result]:
    out: List[Result] = []
    data = manifest_mod.load()
    if data is None:
        return [Result("FAIL", "L2", "MANIFEST.json 缺失或无法解析，请运行 tools/manifest.py generate")]

    if data.get("schema") != manifest_mod.SCHEMA_VERSION:
        out.append(Result("FAIL", "L2", f"清单 schema={data.get('schema')}，期望 {manifest_mod.SCHEMA_VERSION}"))
    else:
        out.append(Result("PASS", "L2", f"清单可解析（schema={data.get('schema')}，生成于 {data.get('generated_at')}）"))

    on_disk = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
    recorded = [s["name"] for s in data["skills"]]  # type: ignore[index]

    # L3 名字集合双向一致
    missing = sorted(set(on_disk) - set(recorded))
    extra = sorted(set(recorded) - set(on_disk))
    if missing:
        out.append(Result("FAIL", "L3", f"磁盘有但清单无（{len(missing)}）：{', '.join(missing[:8])}"))
    if extra:
        out.append(Result("FAIL", "L3", f"清单有但磁盘无（{len(extra)}）：{', '.join(extra[:8])}"))
    if len(recorded) != len(set(recorded)):
        out.append(Result("FAIL", "L3", "清单中存在重复技能名"))
    if int(data.get("skill_count", -1)) != len(on_disk):
        out.append(Result("FAIL", "L3", f"清单 skill_count={data.get('skill_count')}，磁盘实际 {len(on_disk)}"))
    if not missing and not extra:
        out.append(Result("PASS", "L3", f"技能集合一致（{len(on_disk)} 个）"))

    # L4 内容摘要逐项比对
    drift: List[str] = []
    total_bytes = 0
    for record in data["skills"]:  # type: ignore[index]
        name = record["name"]
        skill_dir = ROOT / "skills" / name
        if not skill_dir.is_dir():
            continue
        digest, files, size = manifest_mod.dir_digest(skill_dir)
        total_bytes += size
        if digest != record["sha256"]:
            drift.append(f"{name}(文件 {record['files']}→{files})")
    if drift:
        out.append(
            Result("FAIL", "L4", f"{len(drift)} 个技能内容已变更但清单未重建：{', '.join(drift[:6])}")
        )
    else:
        out.append(Result("PASS", "L4", f"内容摘要全部匹配（{len(data['skills'])} 个技能）"))

    # L6 体积预算
    if total_bytes > MAX_SKILLS_BYTES:
        out.append(Result("FAIL", "L6", f"技能内容 {total_bytes / 1048576:.2f} MB 超过 {MAX_SKILLS_BYTES // 1048576} MB 预算"))
    else:
        out.append(Result("PASS", "L6", f"技能内容 {total_bytes / 1024:.1f} KB，在预算内"))

    return out


def check_versions() -> List[Result]:
    out: List[Result] = []
    problems = version_mod.check(ROOT)
    if problems:
        for item in problems:
            out.append(Result("FAIL", "L5", item))
        return out

    data = version_mod.read_versions(ROOT)
    manifest_data = manifest_mod.load() or {}
    if manifest_data.get("package_version") != data["package"]:
        out.append(
            Result(
                "FAIL",
                "L5",
                f"MANIFEST.package_version={manifest_data.get('package_version')} 与 versions.json.package={data['package']} 不一致",
            )
        )
    else:
        out.append(Result("PASS", "L5", f"版本对齐（包 v{data['package']}）"))
    return out


def check_skills_layout() -> List[Result]:
    out: List[Result] = []
    loose_files = [p.name for p in (ROOT / "skills").iterdir() if p.is_file()]
    if loose_files:
        out.append(Result("FAIL", "L7", f"skills/ 根下存在游离文件：{', '.join(loose_files[:6])}"))
    else:
        out.append(Result("PASS", "L7", "skills/ 仅含技能目录"))

    empty_dirs = [
        p.name for p in (ROOT / "skills").iterdir() if p.is_dir() and not any(p.iterdir())
    ]
    if empty_dirs:
        out.append(Result("FAIL", "L7", f"空技能目录：{', '.join(empty_dirs)}"))
    return out


def run_all() -> List[Result]:
    results: List[Result] = []
    results += check_required_paths()
    results += check_manifest()
    results += check_versions()
    results += check_skills_layout()
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="清单约束校验")
    parser.add_argument("--warn-as-error", action="store_true")
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(argv)

    results = run_all()
    fails = [r for r in results if r.level == "FAIL"]
    warns = [r for r in results if r.level == "WARN"]

    for r in results:
        if r.level == "PASS":
            continue
        print(f"[{r.level}] {r.code} {r.message}")
    for r in results:
        if r.level == "PASS":
            print(f"[PASS] {r.code} {r.message}")

    print()
    print(f"校验结果：{len(results) - len(fails) - len(warns)} 通过 / {len(warns)} 警告 / {len(fails)} 失败")

    if args.json_out:
        payload = [{"level": r.level, "code": r.code, "message": r.message} for r in results]
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if fails or (args.warn_as_error and warns):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
