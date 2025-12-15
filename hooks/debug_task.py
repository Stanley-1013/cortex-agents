#!/usr/bin/env python3
"""Debug hook to capture Task tool response format"""
import json
import sys
import os
from datetime import datetime

# 讀取 stdin
try:
    input_data = json.load(sys.stdin)
except:
    sys.exit(0)

# 只處理 Task tool
if input_data.get("tool_name") != "Task":
    sys.exit(0)

# 寫入 debug log
log_path = os.path.expanduser("~/.claude/neuromorphic/hooks/task_debug.log")
with open(log_path, "a") as f:
    f.write(f"\n{'='*60}\n")
    f.write(f"Timestamp: {datetime.now().isoformat()}\n")
    f.write(f"{'='*60}\n")
    f.write(json.dumps(input_data, indent=2, ensure_ascii=False, default=str))
    f.write("\n")

sys.exit(0)
