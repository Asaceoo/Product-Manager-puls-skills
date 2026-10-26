#!/usr/bin/env python3
"""打包流水线：递增版本 → 重建清单 → 审查 → 校验 → 打包 → 出校验和。

门禁顺序（任一环节失败即中止，不产出 zip）
------------------------------------------
1. ``version.bump``      递增包版本与三份文档版本（可用 --no-bump 跳过）
2. ``manifest.generate`` 重建 MANIFEST.json，使摘要与磁盘一致
3. ``audit``             三视角对抗审查，P0/P1 必须为 0
4. ``validate``          清单约束兜底，必须全 PASS
5. ``changelog``         追加本次发布条目（必须在打包前，否则 zip 里缺本版记录）
6. package               生成 dist/*.zip 与 SHA256SUMS.txt

CLI
---
    python tools/build.py                     # 完整发布流程（patch +1）
    python tools/build.py --part minor
    python tools/build.py --no-bump           # 重打包，版本不变
    python tools/build.py --skip-audit        # 仅调试用，正式发布不得跳过
    python tools/build.py --dry-run           # 只跑门禁，不打包
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manifest as manifest_mod  # noqa: E402
import version as version_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DIST = ROOT / "dist"
PKG_SLUG = "Product-Manager-puls-skills"
CST = timezone(timedelta(hours=8))

#: 打进 zip 的顶层条目
INCLUDE = (
    "README.md",
    "CHANGELOG.md",
    "VERSION",
    "versions.json",
    "LICENSE",
    "NOTICE",
    "MANIFEST.json",
    "skills",
    "catalog",
    "docs",
    "tools",
)

#: 打包时忽略的路径片段
EXCLUDE_PARTS = {"__pycache__", ".git", ".pytest_cache", "reports", "dist"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".tmp", ".log"}


def run_tool(name: str, *args: str) -> Tuple[int, str]:
    """调用 tools/ 下的脚本，返回 (退出码, 输出)。"""
    cmd = [sys.executable, str(TOOLS / name), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


def collect_files() -> List[Path]:
    """收集待打包文件，保持稳定顺序。"""
    files: List[Path] = []
    for entry in INCLUDE:
        path = ROOT / entry
        if not path.exists():
            raise FileNotFoundError(f"打包清单中的路径不存在：{entry}")
        if path.is_file():
            files.append(path)
            continue
        for item in sorted(path.rglob("*")):
            if not item.is_file():
                continue
            if EXCLUDE_PARTS & set(item.parts):
                continue
            if item.suffix in EXCLUDE_SUFFIX:
                continue
            files.append(item)
    return files


def build_package(package_version: str) -> Tuple[Path, Path, int, int]:
    """生成 zip 与校验和文件，返回 (zip 路径, 校验和路径, 文件数, 字节数)。"""
    DIST.mkdir(parents=True, exist_ok=True)
    zip_path = DIST / f"{PKG_SLUG}-v{package_version}.zip"
    inner_root = f"{PKG_SLUG}-v{package_version}"

    files = collect_files()
    total_bytes = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = f"{inner_root}/{path.relative_to(ROOT).as_posix()}"
            zf.write(path, arcname)
            total_bytes += path.stat().st_size

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sums = DIST / "SHA256SUMS.txt"
    line = f"{digest}  {zip_path.name}\n"
    if sums.exists():
        kept = [
            row
            for row in sums.read_text(encoding="utf-8").splitlines()
            if row.strip() and not row.endswith(f"  {zip_path.name}")
        ]
        line = "\n".join(kept + [line.strip()]) + "\n"
    sums.write_text(line, encoding="utf-8", newline="\n")

    return zip_path, sums, len(files), total_bytes


def append_changelog(package_version: str, docs: dict, stats: dict, skill_count: int) -> None:
    """在 CHANGELOG.md 顶部插入本次发布条目（保留历史）。"""
    path = ROOT / "CHANGELOG.md"
    today = datetime.now(CST).strftime("%Y-%m-%d")
    entry = (
        f"## v{package_version} — {today}\n\n"
        f"- 包版本 `v{package_version}`；用户手册 `v{docs['user_manual']}`；技术手册 `v{docs['tech_manual']}`\n"
        f"- 技能 {skill_count} 个，审查 P0={stats.get('P0', 0)} / P1={stats.get('P1', 0)} / P2={stats.get('P2', 0)}\n"
        f"- 资源包：`{PKG_SLUG}-v{package_version}.zip`\n\n"
    )
    header = "# CHANGELOG\n\n本文件由 `tools/build.py` 自动追加，每条对应一次打包。\n\n"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        body = text.split("\n\n", 2)
        rest = text[len(header):] if text.startswith(header) else text
        path.write_text(header + entry + rest, encoding="utf-8", newline="\n")
    else:
        path.write_text(header + entry, encoding="utf-8", newline="\n")


def parse_audit_summary(output: str) -> dict:
    """从 audit 输出里取 P0/P1/P2 计数。"""
    stats = {"P0": 0, "P1": 0, "P2": 0}
    for line in output.splitlines():
        if line.startswith("结果："):
            for part in line.replace("结果：", "").split():
                if "=" in part:
                    key, _, value = part.partition("=")
                    if key in stats and value.isdigit():
                        stats[key] = int(value)
    return stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="打包流水线")
    parser.add_argument("--part", default="patch", choices=("major", "minor", "patch"))
    parser.add_argument("--no-bump", action="store_true", help="不递增版本，直接重打包")
    parser.add_argument("--skip-audit", action="store_true", help="跳过审查（仅调试）")
    parser.add_argument("--dry-run", action="store_true", help="只跑门禁，不产出 zip")
    parser.add_argument("--allow-p2", action="store_true", help="允许存在 P2 建议项")
    args = parser.parse_args(argv)

    step = 0

    # 1. 版本
    step += 1
    print(f"[{step}/6] 版本号")
    if args.no_bump:
        docs = version_mod.read_versions(ROOT)
        print(f"      跳过递增，沿用 v{docs['package']}")
    else:
        docs = version_mod.bump(ROOT, part=args.part)
        print(f"      包 v{docs['package']}  手册 v{docs['user_manual']}  技术手册 v{docs['tech_manual']}")
    package_version = docs["package"]

    # 2. 清单
    step += 1
    print(f"[{step}/6] 清单")
    data = manifest_mod.generate()
    print(f"      技能 {data['skill_count']} 个 / 文件 {data['total_files']} 个 / "
          f"{int(data['total_bytes']) / 1024:.1f} KB")

    # 3. 审查
    step += 1
    print(f"[{step}/6] 三视角审查")
    stats = {"P0": 0, "P1": 0, "P2": 0}
    if args.skip_audit:
        print("      [WARN] 已跳过 —— 仅限本地调试，发布不可跳过")
    else:
        code, output = run_tool("audit.py", "--json", "reports/audit-build.json")
        stats = parse_audit_summary(output)
        print(f"      P0={stats['P0']}  P1={stats['P1']}  P2={stats['P2']}")
        if code != 0 and stats["P0"] + stats["P1"] > 0:
            print(output)
            print("[ABORT] 审查未通过（存在 P0/P1），已中止打包", file=sys.stderr)
            return 1
        if stats["P2"] > 0 and not args.allow_p2:
            print(f"      [WARN] 仍有 {stats['P2']} 项 P2 建议，继续流程（可用 --allow-p2 显式确认）")

    # 4. 校验
    step += 1
    print(f"[{step}/6] 清单约束校验")
    code, output = run_tool("validate.py")
    if code != 0:
        print(output)
        print("[ABORT] 校验未通过，已中止打包", file=sys.stderr)
        return 1
    tail = [l for l in output.strip().splitlines() if l.startswith("校验结果")]
    print(f"      {tail[0] if tail else '通过'}")

    if args.dry_run:
        print("\n[DRY-RUN] 门禁全部通过，未产出 zip")
        return 0

    # 5. 变更日志（必须在打包之前：zip 内要包含本次条目）
    step += 1
    print(f"[{step}/6] CHANGELOG")
    append_changelog(package_version, docs, stats, int(data["skill_count"]))
    print(f"      已追加 v{package_version} 条目")

    # 6. 打包
    step += 1
    print(f"[{step}/6] 打包")
    zip_path, sums, file_count, total_bytes = build_package(package_version)
    print(f"      {zip_path.name}  {zip_path.stat().st_size / 1024:.1f} KB（源 {file_count} 文件 / "
          f"{total_bytes / 1024:.1f} KB）")
    print(f"      {sums.name}")

    print()
    print(f"发布就绪：v{package_version}")
    print(f"  资源包 {zip_path}")
    print(f"  校验和 {sums.read_text(encoding='utf-8').strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
