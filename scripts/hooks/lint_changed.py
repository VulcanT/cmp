"""PostToolUse hook: run ruff on the file that was just edited (Python files only)."""

import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = str(payload.get("tool_input", {}).get("file_path", ""))
    if not path.endswith(".py") or shutil.which("ruff") is None:
        return 0
    result = subprocess.run(["ruff", "check", "--fix", path], capture_output=True, text=True)
    subprocess.run(["ruff", "format", path], capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
