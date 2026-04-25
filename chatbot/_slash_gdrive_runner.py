# _slash_gdrive_runner.py
import subprocess
from pathlib import Path
import sys

def run_gdrive(args):
    try:
        script_path = Path("tools/gdrive.py")
        if not script_path.exists():
            raise FileNotFoundError("tools/gdrive.py not found.") 
        
        process = subprocess.run([sys.executable, script_path.as_posix()] + args, capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent, timeout=90)
        if process.stdout:
            return process.stdout
        elif process.stderr:
            return f"[{process.stderr}]" 
        else:
            return "[ERROR] /gdrive 실행 결과가 비어 있습니다."

    except subprocess.TimeoutExpired:
        return "⏱️ /gdrive 실행 시간이 초과되었습니다. `python tools/gdrive.py --init-auth` 를 확인해주세요."
    except ModuleNotFoundError as e:
        if 'google' in str(e):
            return f"pip install google-api-python-client google-auth google-auth-oauthlib 가 필요합니다. {e}"
        else: 
            raise e

if __name__ == "__main__":
    args = ['--max-depth', '2', '--max-items', '80']  
    user_input = input() 
    if user_input:
        args.extend(user_input.split())

    result = run_gdrive(args)
    print(result)