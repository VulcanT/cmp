"""PreToolUse hook: block edits under src/cmp/executor/ unless ALLOW_EXECUTOR_EDIT=1.

Claude Code passes the tool input as JSON on stdin. Exit 2 blocks the tool call and
feeds stderr back to Claude as the reason.
"""

import json
import os
import sys

PROTECTED = "src/cmp/executor/"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = str(payload.get("tool_input", {}).get("file_path", ""))
    if PROTECTED in path.replace("\\", "/") and os.environ.get("ALLOW_EXECUTOR_EDIT") != "1":
        sys.stderr.write(
            f"Blocked: {path} is under {PROTECTED}. The executor is the only code that writes to "
            "Apple Ads. Re-run with ALLOW_EXECUTOR_EDIT=1 after reading specs/executor.md.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
