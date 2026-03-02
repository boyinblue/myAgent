# Ollama CLI 기반 AI 비서

이 폴더에는 Ollama CLI를 이용해 간단한 AI 비서를 구성하는 예제가 포함되어 있습니다.

> **주의:** 가능한 한 **한글로 답변**하세요. 새로운 세션에서는 이전 대화 내용이 유지되지 않으므로, 중요한 규칙은 문서에 기록해 두세요.
>
> 한글이 포함된 문서는 **UTF-8**로 인코딩되어야 합니다. 소스 코드 내 주석에 한글을 쓸 경우에도 인코딩을 명시하세요.

## 1. 설정

`config.json` 파일을 통해 스크립트의 동작을 설정할 수 있습니다.

```json
{
    "model": "gemma2:9b",
    "rag_settings": {
        "docs_path": "../archive"
    }
}
```

- `model`: 사용할 Ollama 모델의 이름입니다.
- `rag_settings.docs_path`: RAG 기능에 사용할 문서들이 저장된 디렉토리의 경로입니다.


## 2. PowerShell 스크립트: ask-assistant.ps1

`ask-assistant.ps1`는 Ollama와 상호작용하는 다용도 PowerShell 스크립트입니다. 직접적인 프롬프트와 파일 기반 입력을 모두 지원하여 빠른 질문부터 상세한 내용 분석까지 다양한 작업에 이상적입니다.

### 사용법

#### 직접 프롬프트 입력
간단한 질문을 할 때 사용합니다.

```powershell
./ask-assistant.ps1 -prompt "Hello, who are you?"
```

#### 파일 입력
파일의 내용을 분석하도록 요청할 때 사용합니다.

```powershell
./ask-assistant.ps1 -filePath "C:\path\to\your\document.txt"
```

## 3. Python 스크립트: chat_assistant.py

`chat_assistant.py`는 RAG(Retrieval-Augmented Generation)와 확장 가능한 스킬 시스템을 갖춘 대화형 AI 비서입니다.

### 1. 개발 환경 설정 및 패키지 설치

Python 가상 환경을 설정하고 필요한 패키지를 설치합니다.

```powershell
# Windows
.\setup_env.ps1

# Linux/macOS
./setup_env.sh
```

`requirements.txt` 파일에는 다음과 같은 패키지가 포함되어야 합니다.

```
ollama
langchain
langchain_community
faiss-cpu
```

### 2. 스크립트 실행

다음과 같이 스크립트를 실행하여 AI 비서를 시작할 수 있습니다.

```bash
python chat_assistant.py
```

**옵션:**
- `--model`: 사용할 Ollama 모델을 지정합니다. (기본값: `config.json` 설정)
- `--docs_path`: RAG 문서 경로를 지정합니다. (기본값: `config.json` 설정)

### 3. 기능

#### RAG (Retrieval-Augmented Generation)

`docs_path`에 지정된 디렉토리의 문서를 기반으로 질문에 답변합니다. 문서가 없거나 경로가 잘못된 경우, 일반적인 대화 모드로 작동합니다.

#### 스킬 (Skills)

특정 키워드를 입력하여 사전에 정의된 작업을 수행할 수 있습니다.

**사용 가능한 스킬:**

- **`git commit`**: `git`에 스테이징된 변경 사항을 기반으로 커밋 메시지를 자동으로 생성하고, 사용자 확인 후 커밋을 수행합니다.
    1.  `git add`를 통해 변경 사항을 스테이징합니다.
    2.  `chat_assistant.py`를 실행하고 프롬프트에 `git commit`을 입력합니다.
    3.  생성된 커밋 메시지를 확인하고 `y`를 입력하여 커밋을 완료합니다.


---

### 추가 설치 안내

#### Ollama 설치
1. 공식 웹사이트(https://ollama.com)에서 설치 안내를 확인합니다.
2. Windows에서는 설치 프로그램을 내려 받아 설치하거나 `choco install ollama` 같은 패키지 관리자를 사용하세요.
3. 리눅스/맥OS에서는 `brew install ollama` 또는 제공되는 바이너리를 이용합니다.
4. 설치 후 `ollama --version` 명령으로 제대로 동작하는지 확인합니다.

#### Python 3 설치
- Windows: https://www.python.org/downloads/windows/ 에서 설치 프로그램을 다운받아 설치하고
  “Add Python to PATH” 옵션을 체크합니다.
- macOS: `brew install python` 또는 https://www.python.org/downloads/macos/ 을 이용하세요.
- Linux: 배포판 패키지(`apt install python3` 등) 또는 `pyenv` 등을 사용합니다.

설치 후에는 `python --version` 또는 `python3 --version`을 통해 버전을 확인해 주세요.
