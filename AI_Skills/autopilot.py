import requests
import re
import sys
from urllib.parse import unquote

def ask_ollama_and_run(prompt):
    # 1. Ollama API 설정 (로컬에 Ollama가 실행 중이어야 함)
    url = "http://localhost:11434/api/generate"
    
    # 프롬프트 엔지니어링: 파일명 주석 및 순수 코드 출력 강제
    system_prompt = (
        "You are a Python code generator. "
        "The first line of your response must be a comment with an appropriate python filename (e.g., # script_name.py). "
        "Respond ONLY with valid Python code. "
        "Do not include any explanations, comments (except for the first line filename), or markdown formatting like ```python. "
        "Ensure all necessary libraries are imported."
    )
    
    data = {
        "model": "gemma2:9b",  # 설치된 모델명 (gemma2, mistral 등 가능)
        "prompt": f"{system_prompt}\n\nTask: {prompt}",
        "stream": False
    }

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        raw_output = response.json().get('response', '').strip()

        script_name = extract_python_code(raw_output)

    except:
        print("[ERROR] Ollama API 요청 실패")
        return None
    
    if script_name:
        try:
            exec(open(script_name).read())
        except Exception as e:
            print(f"[ERROR] '{script_name}' 실행 중 오류: {e}")

# Ollama의 응답에서 코드 블록을 추출해서 파일로 저장한 후 파일명을 반환하는 함수
def extract_python_code(raw_text):
    """
    마크다운 코드 블록 구분선(```)이 포함된 라인을 제거하고 내부 코드만 반환합니다.
    """
    lines = raw_text.split('\n')
    code_lines = []
    script_name = ""
    
    for line in lines:
        # ```로 시작하는 라인은 제외 (python 등의 언어 선언 포함)
        if line.strip().startswith('```'):
            continue
        # 첫 번째 라인이 파일명 주석인 경우 추출
        if not script_name and line.strip().startswith('# '):
            script_name = line.strip()[2:]
        code_lines.append(line)

    # code_lines를 script_name이라는 파일명으로 저장
    if script_name:
        with open(script_name, 'w', encoding='utf-8') as f:
            f.write('\n'.join(code_lines).strip())

    return script_name

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python autopilot.py <task_description>")
        sys.exit(1)

    task_description = " ".join(sys.argv[1:])
    ask_ollama_and_run(task_description)