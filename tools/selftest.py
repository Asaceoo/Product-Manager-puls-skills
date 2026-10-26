#!/usr/bin/env python3
"""功能自检 —— 把"常规验证"从人肉执行变成一条命令。

覆盖四个层面
------------
1. **接口可用**：每个 CLI 的 ``--help`` 必须退出 0，参数名不得拼错
2. **异常路径**：非法输入必须给出非零退出码，而不是静默通过
3. **幂等性**：重复执行不产生差异（``manifest generate`` 两次内容一致）
4. **正常态**：审查与校验在干净仓库上应全通过

全部只读或幂等写，可以随时在正式仓库里跑，也可以挂进 CI。

CLI
---
    python tools/selftest.py            # 静默模式，只报结论
    python tools/selftest.py -v         # 逐项打印
    python tools/selftest.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
SCRIPTS = ROOT / "scripts"

#: tools/ 下的 CLI 与其"应当失败"的调用
TOOL_CASES = {
    "version.py": ("bump", "--keys", "nonexistent_key"),
    "manifest.py": ("bad-command",),
    "audit.py": ("--perspective", "Z"),
    "validate.py": ("--bad-flag",),
    "install.py": ("install", "--only", "zz-no-such-skill"),
}

#: scripts/ 下的关键子命令
SKILLCTL_SUBS = ("find", "metadata", "triggers", "test", "zip", "validate", "catalog", "freshness")


@dataclass
class Case:
    name: str
    ok: bool
    detail: str
    kind: str  # interface / error-path / idempotent / healthy


def run(cmd: Sequence[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd, timeout=180
    )


def check_interface() -> List[Case]:
    """每个 CLI 的 --help 必须可用。"""
    out: List[Case] = []
    targets = sorted(TOOLS.glob("*.py")) + sorted(SCRIPTS.glob("*.py"))
    for path in targets:
        rel = path.relative_to(ROOT).as_posix()
        proc = run([sys.executable, str(path), "--help"])
        ok = proc.returncode == 0 and "usage" in (proc.stdout + proc.stderr).lower()
        out.append(Case(f"{rel} --help", ok, f"退出码 {proc.returncode}", "interface"))
    return out


def check_error_paths() -> List[Case]:
    """非法输入必须失败，且失败信息不含 traceback。"""
    out: List[Case] = []
    for name, args in TOOL_CASES.items():
        path = TOOLS / name
        proc = run([sys.executable, str(path), *args])
        combined = proc.stdout + proc.stderr
        no_crash = proc.returncode != 0 and "Traceback" not in combined
        out.append(
            Case(
                f"{name} 拒绝非法输入",
                no_crash,
                f"退出码 {proc.returncode}" + ("，含 traceback" if "Traceback" in combined else ""),
                "error-path",
            )
        )
    return out


def check_idempotent() -> List[Case]:
    """manifest generate 重复执行必须产出相同内容。"""
    out: List[Case] = []
    target = ROOT / "MANIFEST.json"
    if not target.exists():
        return [Case("manifest 幂等", False, "MANIFEST.json 不存在", "idempotent")]

    before = target.read_text(encoding="utf-8")
    # generated_at 会变，比较时剔除该字段

    def normalized(text: str) -> str:
        return re.sub(r'"generated_at":\s*"[^"]*"', '"generated_at": "X"', text)

    proc = run([sys.executable, str(TOOLS / "manifest.py"), "generate"])
    after = target.read_text(encoding="utf-8")
    same = normalized(before) == normalized(after)
    out.append(
        Case("manifest 幂等", proc.returncode == 0 and same,
             "内容一致" if same else "两次生成结果不同", "idempotent")
    )
    return out


def check_healthy() -> List[Case]:
    """审查与校验在干净仓库上必须通过。"""
    out: List[Case] = []

    audit = run([sys.executable, str(TOOLS / "audit.py")])
    summary = [l for l in audit.stdout.splitlines() if l.startswith("结果：")]
    detail = summary[0] if summary else "无输出"
    zero = "P0=0" in audit.stdout and "P1=0" in audit.stdout
    out.append(Case("audit 无 P0/P1", audit.returncode == 0 and zero, detail, "healthy"))

    validate = run([sys.executable, str(TOOLS / "validate.py")])
    out.append(
        Case("validate 全通过", validate.returncode == 0,
             "9 条规则通过" if validate.returncode == 0 else "存在 FAIL", "healthy")
    )

    version = run([sys.executable, str(TOOLS / "version.py"), "check"])
    out.append(
        Case("版本四环一致", version.returncode == 0, version.stdout.strip()[:60] or "无输出", "healthy")
    )

    if SCRIPTS.is_dir():
        skillctl = SCRIPTS / "skillctl.py"
        for sub in SKILLCTL_SUBS:
            proc = run([sys.executable, str(skillctl), sub, "--help"])
            ok = proc.returncode == 0
            out.append(Case(f"skillctl {sub} --help", ok, f"退出码 {proc.returncode}", "healthy"))
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="功能自检：接口 / 异常路径 / 幂等 / 正常态")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(argv)

    cases: List[Case] = []
    cases += check_interface()
    cases += check_error_paths()
    cases += check_idempotent()
    cases += check_healthy()

    failed = [c for c in cases if not c.ok]
    if args.verbose:
        for c in cases:
            print(f"[{'PASS' if c.ok else 'FAIL'}] {c.kind:<10} {c.name}  {c.detail}")
    else:
        for c in failed:
            print(f"[FAIL] {c.kind:<10} {c.name}  {c.detail}")

    kinds: dict = {}
    for c in cases:
        bucket = kinds.setdefault(c.kind, [0, 0])
        bucket[0 if c.ok else 1] += 1

    print()
    for kind, (ok, bad) in kinds.items():
        print(f"  {kind:<10} {ok} 通过 / {bad} 失败")
    print(f"\n合计 {len(cases)} 项，{len(cases) - len(failed)} 通过，{len(failed)} 失败")

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps([asdict(c) for c in cases], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
