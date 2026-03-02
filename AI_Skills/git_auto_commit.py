import subprocess
import requests
import json
import sys

# --- [사용자 환경 맞춤 설정] ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
#MODEL_NAME = "gemma2:9b-instruct-q4_K_M"
MODEL_NAME = "gemma2:9b"

def run_command(command):
    """터미널 명령어를 실행하고 결과를 반환합니다."""
    try:
        # 인코딩 이슈 방지를 위해 utf-8 지정
        result = subprocess.run(command, capture_output=True, text=True, shell=True, encoding='utf-8')
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_git_diff():
    """현재 스테이징된 변경사항을 가져옵니다."""
    diff = run_command("git diff --cached")
    
    if not diff:
        status = run_command("git status --porcelain")
        if not status:
            return None
            
        print("💡 스테이징된 변경사항이 없어 'git add .'를 먼저 실행합니다.")
        run_command("git add .")
        diff = run_command("git diff --cached")
        
    return diff

def generate_commit_message(diff):
    """로컬 Ollama를 통해 커밋 메시지를 생성합니다."""
    prompt = f"""
    당신은 전문 소프트웨어 엔지니어입니다. 아래의 git diff 내용을 보고 요약된 커밋 메시지를 작성하세요.
    반드시 'type: description' 형식(예: feat: add youtube api integration)으로 작성하고, 영어로 대답하세요.
    다른 설명 없이 메시지만 딱 한 줄 출력하세요.

    DIFF CONTENT:
    {diff[:3000]}
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()['response'].strip().replace('"', '').replace("'", "")
    except Exception as e:
        return f"fix: update local changes (ai-error: {e})"

def main():
    diff = get_git_diff()
    if not diff:
        print("❌ 변경사항이 감지되지 않았습니다.")
        return

    print(f"📄 감지된 변경사항:\n{diff[:500]}...\n")

    print(f"🤖 로컬 AI({MODEL_NAME})가 GPU로 변경점을 분석 중입니다...")
    commit_msg = generate_commit_message(diff)
    
    print(f"\n✨ 제안된 메시지: {commit_msg}")
    confirm = input("👉 이 메시지로 커밋하시겠습니까? (y/n): ").lower()
    
    if confirm == 'y':
        # 따옴표 포함 메시지 처리를 위해 f-string 내 이스케이프 적용
        success = run_command(f'git commit -m "{commit_msg}"')
        print(f"\n🚀 결과:\n{success}")
        print("\n✅ 커밋 완료!")
    else:
        print("✖️ 커밋이 취소되었습니다.")

if __name__ == "__main__":
    main()