#!/usr/bin/env python3
"""版本号单一事实源（Single Source of Truth）。

职责
----
1. 维护 ``versions.json`` —— 包版本与三份文档（README / 用户手册 / 技术手册）版本。
2. 把版本号注入文档中的标记位，避免任何手工改版本。
3. 校验 ``VERSION`` 文件与文档标记是否与 ``versions.json`` 一致。

标记语法（单行，可被任意 Markdown 解析器忽略）::

    <!--VER:package-->1.0.0<!--/VER-->

CLI
---
    python tools/version.py show
    python tools/version.py bump --part patch
    python tools/version.py bump --part minor --keys package,readme
    python tools/version.py sync
    python tools/version.py check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = ROOT / "versions.json"
VERSION_FILE = ROOT / "VERSION"

#: 需要注入版本号的文档（相对路径）
DOC_FILES: Tuple[str, ...] = (
    "README.md",
    "docs/USER-MANUAL.md",
    "docs/TECH-MANUAL.md",
)

#: versions.json 中受管理的键
VERSION_KEYS: Tuple[str, ...] = ("package", "readme", "user_manual", "tech_manual")

MARK_RE = re.compile(r"<!--VER:(?P<key>[a-z_]+)-->.*?<!--/VER-->")
SEMVER_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


class VersionError(RuntimeError):
    """版本号读写或标记注入失败。"""


# --------------------------------------------------------------------------- #
# 基础读写
# --------------------------------------------------------------------------- #
def read_versions(root: Path = ROOT) -> Dict[str, str]:
    """读取 versions.json，缺失时返回默认全 0.0.0 结构。"""
    path = root / "versions.json"
    if not path.exists():
        raise VersionError(f"缺少版本清单：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - 结构损坏才会触发
        raise VersionError(f"versions.json 不是合法 JSON：{exc}") from exc

    missing = [k for k in VERSION_KEYS if k not in data]
    if missing:
        raise VersionError(f"versions.json 缺少键：{', '.join(missing)}")
    for key in VERSION_KEYS:
        if not SEMVER_RE.match(str(data[key])):
            raise VersionError(f"versions.json 中 {key}={data[key]!r} 不是 MAJOR.MINOR.PATCH")
    return data


def write_versions(data: Dict[str, str], root: Path = ROOT) -> None:
    """原子写入 versions.json，键顺序固定。"""
    ordered = {k: data[k] for k in VERSION_KEYS}
    for extra in ("released_at",):
        if extra in data:
            ordered[extra] = data[extra]
    payload = json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"
    _atomic_write(root / "versions.json", payload)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# 语义化递增
# --------------------------------------------------------------------------- #
def bump_semver(version: str, part: str = "patch") -> str:
    """按 part 递增语义化版本号。"""
    match = SEMVER_RE.match(version)
    if not match:
        raise VersionError(f"非法版本号：{version!r}")
    major, minor, patch = (int(match.group(g)) for g in ("major", "minor", "patch"))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise VersionError(f"不支持的递增类型：{part!r}（可选 major/minor/patch）")
    return f"{major}.{minor}.{patch}"


def bump(root: Path = ROOT, part: str = "patch", keys: Iterable[str] | None = None) -> Dict[str, str]:
    """递增指定键的版本号并落盘，返回递增后的完整版本表。"""
    data = read_versions(root)
    targets: List[str] = list(keys) if keys else list(VERSION_KEYS)
    unknown = [k for k in targets if k not in VERSION_KEYS]
    if unknown:
        raise VersionError(f"未知版本键：{', '.join(unknown)}")
    for key in targets:
        data[key] = bump_semver(str(data[key]), part)
    write_versions(data, root)
    sync(root, data)
    return data


# --------------------------------------------------------------------------- #
# 注入与校验
# --------------------------------------------------------------------------- #
def inject(text: str, values: Dict[str, str]) -> Tuple[str, int, List[str]]:
    """把 values 注入文本标记位，返回 (新文本, 替换次数, 未知键列表)。"""
    count = 0
    unknown: List[str] = []

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        key = match.group("key")
        if key not in values:
            unknown.append(key)
            return match.group(0)
        count += 1
        return f"<!--VER:{key}-->{values[key]}<!--/VER-->"

    return MARK_RE.sub(_sub, text), count, unknown


def sync(root: Path = ROOT, data: Dict[str, str] | None = None) -> Dict[str, int]:
    """把版本号同步到 VERSION 文件与全部文档标记位。

    返回 {文件名: 替换次数}。文件不存在时跳过（文档分批落地时仍可运行）。
    """
    data = data or read_versions(root)
    values = {k: str(data[k]) for k in VERSION_KEYS}

    _atomic_write(root / "VERSION", values["package"] + "\n")

    stats: Dict[str, int] = {}
    for rel in DOC_FILES:
        path = root / rel
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated, count, unknown = inject(original, values)
        if unknown:
            raise VersionError(f"{rel} 存在未知版本标记：{sorted(set(unknown))}")
        if updated != original:
            _atomic_write(path, updated)
        stats[rel] = count
    return stats


def check(root: Path = ROOT) -> List[str]:
    """校验一致性，返回问题列表（空表示通过）。"""
    problems: List[str] = []
    try:
        data = read_versions(root)
    except VersionError as exc:
        return [str(exc)]

    version_file = root / "VERSION"
    if not version_file.exists():
        problems.append("缺少 VERSION 文件")
    else:
        actual = version_file.read_text(encoding="utf-8").strip()
        if actual != data["package"]:
            problems.append(f"VERSION({actual}) 与 versions.json.package({data['package']}) 不一致")

    values = {k: str(data[k]) for k in VERSION_KEYS}
    for rel in DOC_FILES:
        path = root / rel
        if not path.exists():
            problems.append(f"缺少文档：{rel}")
            continue
        text = path.read_text(encoding="utf-8")
        found = MARK_RE.findall(text)
        if not found:
            problems.append(f"{rel} 中没有任何版本标记")
            continue
        for match in MARK_RE.finditer(text):
            key = match.group("key")
            actual = match.group(0).split("-->")[1].rsplit("<!--", 1)[0]
            if key not in values:
                problems.append(f"{rel} 含未知标记键 {key}")
            elif actual != values[key]:
                problems.append(f"{rel} 的 {key} 标记为 {actual}，应为 {values[key]}")
    return problems


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_keys(raw: str | None) -> List[str] | None:
    if not raw:
        return None
    return [k.strip() for k in raw.split(",") if k.strip()]


def main(argv: List[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="版本号管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show", help="打印当前版本表")

    p_bump = sub.add_parser("bump", help="递增版本号")
    p_bump.add_argument("--part", default="patch", choices=("major", "minor", "patch"))
    p_bump.add_argument("--keys", default=None, help="逗号分隔，默认全部")

    sub.add_parser("sync", help="同步 VERSION 与文档标记")
    sub.add_parser("check", help="校验一致性")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "show":
            data = read_versions()
            for key in VERSION_KEYS:
                print(f"{key:<13} v{data[key]}")
            return 0
        if args.cmd == "bump":
            data = bump(part=args.part, keys=_parse_keys(args.keys))
            for key in VERSION_KEYS:
                print(f"{key:<13} v{data[key]}")
            return 0
        if args.cmd == "sync":
            stats = sync()
            if not stats:
                print("未找到可注入的文档")
            for name, count in stats.items():
                print(f"{name}: {count} 处标记")
            return 0
        if args.cmd == "check":
            problems = check()
            if problems:
                for item in problems:
                    print(f"[FAIL] {item}")
                return 1
            print("[OK] 版本号一致")
            return 0
    except VersionError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
