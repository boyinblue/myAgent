import requests

from runtime_config import get_config_value
from shared_credentials import get_shared_secret


def _first_valid(*candidates: str) -> str:
    for value in candidates:
        normalized = (value or "").strip()
        if not normalized:
            continue
        if normalized.lower() in {"owner/repo", "your/repo", "<owner>/<repo>"}:
            continue
        if normalized.lower() in {"run_workflow.yml", "workflow.yml", "your-workflow.yml"}:
            continue
        return normalized
    return ""


def _diagnose_not_found(repo: str, workflow: str, ref: str, headers: dict) -> str:
    try:
        repo_resp = requests.get(
            f"https://api.github.com/repos/{repo}",
            headers=headers,
            timeout=20,
        )
    except Exception as exc:
        return f"추가 진단 실패(리포 조회): {exc}"

    if repo_resp.status_code == 404:
        return (
            "리포를 찾지 못했거나 토큰이 해당 리포에 접근할 수 없습니다. "
            "토큰의 저장소 접근 권한과 repo 설정을 확인하세요."
        )

    if repo_resp.status_code in {401, 403}:
        return "토큰 인증/권한 문제로 리포 조회에 실패했습니다."

    try:
        wf_resp = requests.get(
            f"https://api.github.com/repos/{repo}/actions/workflows",
            headers=headers,
            timeout=20,
        )
    except Exception as exc:
        return f"추가 진단 실패(워크플로 목록 조회): {exc}"

    if wf_resp.status_code in {401, 403}:
        return "Actions 조회 권한이 부족합니다. 토큰에 Actions 권한(read/write)을 부여하세요."

    if wf_resp.status_code != 200:
        return f"워크플로 목록 조회 실패(status={wf_resp.status_code})."

    data = wf_resp.json() if wf_resp.content else {}
    workflows = data.get("workflows", []) if isinstance(data, dict) else []

    matched = False
    expected_path = f".github/workflows/{workflow}"
    for item in workflows:
        path = str(item.get("path", "")).strip()
        name = str(item.get("name", "")).strip()
        if path.endswith(f"/{workflow}") or path == expected_path or name == workflow:
            matched = True
            break

    if not matched:
        return (
            f"워크플로 파일 '{workflow}'를 찾지 못했습니다. "
            "파일명/경로(.github/workflows)와 원격 브랜치 반영 여부(push)를 확인하세요."
        )

    return (
        f"리포/워크플로는 확인되었습니다. dispatch ref='{ref}'가 존재하는지, "
        "또는 workflow_dispatch 트리거가 해당 브랜치 버전에 있는지 확인하세요."
    )


def trigger_content_crawler_workflow(target_url: str) -> str:
    token = (get_shared_secret("GITHUB_TOKEN") or "").strip()
    repo = _first_valid(
        str(get_config_value("autopilot.github_dispatch.repo", "")),
        get_shared_secret("GITHUB_REPO", ""),
    )
    workflow = _first_valid(
        str(get_config_value("autopilot.github_dispatch.workflow_file", "")),
        get_shared_secret("GITHUB_WORKFLOW_FILE", "run_crowler.yml"),
        "run_crowler.yml",
    )
    ref = str(
        get_config_value(
            "autopilot.github_dispatch.ref",
            get_shared_secret("GITHUB_REF_NAME", "main"),
        )
    ).strip()

    if not token:
        return "[ERROR] GITHUB_TOKEN이 설정되지 않았습니다."
    if not repo or "/" not in repo:
        return "[ERROR] GitHub repo 설정이 비어있거나 플레이스홀더입니다. content-crawler/config.json의 autopilot.github_dispatch.repo를 실제 owner/repo로 설정하거나, .env의 GITHUB_REPO를 설정하세요."
    if not workflow.endswith(".yml") and not workflow.endswith(".yaml"):
        return "[ERROR] workflow_file 설정이 잘못되었습니다. 예: run_crowler.yml"
    if not target_url:
        return "[ERROR] URL이 비어 있습니다."

    endpoint = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "ref": ref,
        "inputs": {
            "url": target_url,
        },
    }

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    if resp.status_code in {201, 204}:
        return f"[OK] GitHub Actions 디스패치 성공: workflow={workflow}, ref={ref}, url={target_url}"

    body = ""
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:500]

    setup_guide = ""
    if resp.status_code == 401:
        setup_guide = "토큰이 유효하지 않습니다. GITHUB_TOKEN(PAT)을 재발급하고 만료 여부를 확인하세요."
    elif resp.status_code == 403:
        setup_guide = "권한이 부족합니다. 토큰에 Actions: Read and write + 해당 저장소 접근 권한이 필요합니다."
    elif resp.status_code == 404:
        diagnostic = _diagnose_not_found(repo=repo, workflow=workflow, ref=ref, headers=headers)
        setup_guide = (
            "리포/워크플로를 찾지 못했습니다. "
            f"repo={repo}, workflow={workflow}, ref={ref}. "
            f"추가진단: {diagnostic}"
        )
    elif resp.status_code == 422:
        setup_guide = "workflow_dispatch 입력값/브랜치(ref) 또는 URL 형식을 확인하세요."

    detail = body
    if isinstance(body, dict):
        detail = body.get("message") or body

    if setup_guide:
        return (
            f"[ERROR] GitHub Actions 디스패치 실패: status={resp.status_code}, "
            f"workflow={workflow}, ref={ref}, detail={detail}. 가이드: {setup_guide}"
        )

    return (
        f"[ERROR] GitHub Actions 디스패치 실패: status={resp.status_code}, "
        f"workflow={workflow}, ref={ref}, detail={detail}"
    )
