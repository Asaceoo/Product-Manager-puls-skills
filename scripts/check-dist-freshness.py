#!/usr/bin/env python3
"""入口薄壳：签名与上游一致，实现见 skillctl.py。"""
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import skillctl  # noqa: E402

    return skillctl.main(["freshness", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
