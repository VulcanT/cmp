"""Stop hook: do not let a turn end while the test suite is red.

Claude Code reads a JSON object from stdout; {"decision": "block", "reason": ...} keeps the
session working. Guard against infinite loops with stop_hook_active.
"""

import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    if payload.get("stop_hook_active"):
        return 0
    result = subprocess.run(["pytest", "-q", "-x", "--no-header"], capture_output=True, text=True)
    if result.returncode == 0:
        return 0
    tail = "\n".join((result.stdout + result.stderr).splitlines()[-30:])
    print(
        json.dumps(
            {"decision": "block", "reason": f"Tests are failing; fix before stopping:\n{tail}"}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
