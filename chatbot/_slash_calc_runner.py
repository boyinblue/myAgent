# _slash_calc_runner.py
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    args = sys.argv[1:]  
    if not args:
        print("❌ 사용법: /calc <수식>")
        exit()
    try:
        result = subprocess.run(
            [sys.executable, "tools/calc.py"] + args,
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        print("⏱️ /calc 실행 시간이 초과되었습니다.")
        exit()

    if result.stdout:
        print(result.stdout.strip())
    elif result.stderr:
        print(f"[ERROR] {result.stderr.strip()}")