#!/usr/bin/env bash
# 入口薄壳：签名与上游一致，实现见 skillctl.py
set -euo pipefail
exec python3 "$(dirname "$0")/skillctl.py" dist "$@"
