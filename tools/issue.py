import re
from datetime import datetime, timezone

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


def _resolve_github_repo() -> str:
    return _first_valid(
        str(get_config_value("autopilot.github_dispatch.repo", "")),
        get_shared_secret("GITHUB_REPO", ""),
    )


def _build_issue_payload(user_prompt: str) -> tuple[str, str]:
    raw = (user_prompt or "").strip()
    if not raw:
        now = datetime.now(timezone.utc).isoformat()
        return ("챗봇 사용 중 불편사항 제보", f"## 요약\n(내용 없음)\n\n## 원문\n\n\n## 등록 시각(UTC)\n{now}")

    cleaned = raw
    cleanup_patterns = [
        r"github\s*(repo)?\s*issue",
        r"이슈",
        r"issue",
        r"등록(해\s*줘|해주세요|해줘)?",
        r"생성(해\s*줘|해주세요|해줘)?",
        r"올려(줘|주세요)?",
        r"만들어(줘|주세요)?",
        r"작성(해\s*줘|해주세요|해줘)?",
        r"해결(해\s*줘|해주세요|해줘)?",
        r"부탁(해\s*요|해요)?",
    ]
    for pattern in cleanup_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;!?")
    summary = cleaned or raw
    if len(summary) > 120:
        summary = summary[:117].rstrip() + "..."

    title = f"[챗봇 피드백] {summary}"

    now = datetime.now(timezone.utc).isoformat()
    body = (
        "## 요약\n"
        f"{summary}\n\n"
        "## 원문\n"
        f"{raw}\n\n"
        "## 등록 시각(UTC)\n"
        f"{now}\n"
    )
    return title, body


def _resolve_issue_labels() -> list[str]:
    labels_config = get_config_value("autopilot.github_issue.labels", [])
    
    # config.json에서 리스트로 바로 받거나, 쉼표 구분 문자열 처리
    if isinstance(labels_config, list):
        labels = [str(label).strip() for label in labels_config if str(label).strip()]
        return labels if labels else ["chatbot", "feedback"]
    
    configured_str = str(labels_config).strip()
    if not configured_str:
        return ["chatbot", "feedback"]
    
    labels = [token.strip() for token in configured_str.split(",") if token.strip()]
    return labels or ["chatbot", "feedback"]


def _find_similar_issues(repo: str, title: str, token: str, threshold: float = 0.6) -> list[dict]:
    """기존 이슈 중 제목이 유사한 것을 검색합니다."""
    check_duplicates = bool(get_config_value("autopilot.github_issue.check_duplicates", True))
    if not check_duplicates:
        return []

    endpoint = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "state": "all",
        "labels": "chatbot,feedback",
        "per_page": 30,
        "sort": "created",
        "direction": "desc",
    }

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            return []

        issues = resp.json() if resp.content else []
        if not isinstance(issues, list):
            return []

        # 간단한 단어 기반 유사도 계산
        def calc_similarity(title1: str, title2: str) -> float:
            words1 = set(re.findall(r'\w+', title1.lower()))
            words2 = set(re.findall(r'\w+', title2.lower()))
            if not words1 or not words2:
                return 0.0
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            return intersection / union if union > 0 else 0.0

        similar = []
        for issue in issues:
            issue_title = str(issue.get("title", ""))
            similarity = calc_similarity(title, issue_title)
            if similarity >= threshold:
                similar.append({
                    "number": issue.get("number"),
                    "title": issue_title,
                    "state": issue.get("state"),
                    "url": issue.get("html_url"),
                    "similarity": round(similarity, 2),
                })

        return sorted(similar, key=lambda x: x["similarity"], reverse=True)[:3]
    except Exception:
        return []


def _fetch_issue_list(repo: str, token: str, state: str, limit: int = 20) -> tuple[bool, str, list[dict]]:
    endpoint = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "state": state,
        "labels": "chatbot,feedback",
        "per_page": max(1, min(int(limit), 100)),
        "sort": "created",
        "direction": "desc",
    }

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=20)
    except Exception as exc:
        return (False, f"[ERROR] GitHub Issue 목록 조회 실패: {exc}", [])

    if resp.status_code != 200:
        detail = ""
        try:
            body = resp.json()
            detail = body.get("message") if isinstance(body, dict) else str(body)
        except Exception:
            detail = (resp.text or "")[:500]
        return (False, f"[ERROR] GitHub Issue 목록 조회 실패: status={resp.status_code}, detail={detail}", [])

    issues = resp.json() if resp.content else []
    if not isinstance(issues, list):
        return (False, "[ERROR] GitHub Issue 목록 응답 형식이 올바르지 않습니다.", [])

    normalized = []
    for issue in issues:
        # pull request는 제외
        if isinstance(issue, dict) and issue.get("pull_request"):
            continue
        normalized.append(issue)

    return (True, "", normalized)


def _format_issue_list(issues: list[dict], state: str) -> str:
    state_name = "오픈" if state == "open" else "종료"
    if not issues:
        return f"[INFO] 현재 {state_name}된 이슈가 없습니다."

    lines = [f"[{state_name} 이슈] 총 {len(issues)}건"]
    for idx, issue in enumerate(issues, 1):
        number = issue.get("number", "?")
        title = str(issue.get("title", "(제목 없음)")).strip()
        url = str(issue.get("html_url", "")).strip()
        created_at = str(issue.get("created_at", "")).strip()
        closed_at = str(issue.get("closed_at", "")).strip()

        meta = f"created: {created_at}" if created_at else "created: -"
        if state == "closed" and closed_at:
            meta += f" | closed: {closed_at}"

        lines.append(f"{idx}. #{number} {title}")
        if url:
            lines.append(f"   {meta} | {url}")
        else:
            lines.append(f"   {meta}")

    return "\n".join(lines)


def list_github_issues(state: str = "open") -> str:
    normalized_state = (state or "open").strip().lower()
    if normalized_state not in {"open", "closed"}:
        return "[ERROR] state는 open 또는 closed만 지원합니다."

    token = (get_shared_secret("GITHUB_TOKEN") or "").strip()
    repo = _resolve_github_repo()

    if not token:
        return "[ERROR] GITHUB_TOKEN이 설정되지 않았습니다."
    if not repo or "/" not in repo:
        return "[ERROR] GitHub repo 설정이 비어있거나 플레이스홀더입니다. content-crawler/config.json의 autopilot.github_dispatch.repo를 실제 owner/repo로 설정하거나, .env의 GITHUB_REPO를 설정하세요."

    limit = int(get_config_value("autopilot.github_issue.list_limit", 20))
    ok, message, issues = _fetch_issue_list(repo=repo, token=token, state=normalized_state, limit=limit)
    if not ok:
        return message

    return _format_issue_list(issues=issues, state=normalized_state)


def list_open_github_issues() -> str:
    return list_github_issues("open")


def list_closed_github_issues() -> str:
    return list_github_issues("closed")


def create_github_issue_from_feedback(user_prompt: str) -> str:
    token = (get_shared_secret("GITHUB_TOKEN") or "").strip()
    repo = _resolve_github_repo()

    if not token:
        return "[ERROR] GITHUB_TOKEN이 설정되지 않았습니다."
    if not repo or "/" not in repo:
        return "[ERROR] GitHub repo 설정이 비어있거나 플레이스홀더입니다. content-crawler/config.json의 autopilot.github_dispatch.repo를 실제 owner/repo로 설정하거나, .env의 GITHUB_REPO를 설정하세요."

    title, body = _build_issue_payload(user_prompt)
    labels = _resolve_issue_labels()

    # 유사 이슈 검색
    threshold = float(get_config_value("autopilot.github_issue.similarity_threshold", 0.6))
    similar_issues = _find_similar_issues(repo, title, token, threshold)
    
    if similar_issues:
        result_lines = ["[INFO] 유사한 이슈가 이미 존재합니다. 새 이슈를 생성하지 않았습니다.\n"]
        for idx, issue in enumerate(similar_issues, 1):
            state_emoji = "🟢" if issue["state"] == "open" else "🔴"
            result_lines.append(
                f"{idx}. {state_emoji} #{issue['number']}: {issue['title']}\n"
                f"   유사도: {issue['similarity']*100:.0f}% | {issue['url']}"
            )
        return "\n".join(result_lines)

    endpoint = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": labels,
    }

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)

    if resp.status_code == 201:
        data = resp.json() if resp.content else {}
        issue_url = data.get("html_url", "") if isinstance(data, dict) else ""
        issue_number = data.get("number", "") if isinstance(data, dict) else ""
        return f"[OK] GitHub Issue 생성 성공: #{issue_number} {issue_url}".strip()

    detail = ""
    try:
        body_data = resp.json()
        detail = body_data.get("message") if isinstance(body_data, dict) else str(body_data)
    except Exception:
        detail = (resp.text or "")[:500]

    guide = ""
    if resp.status_code == 401:
        guide = "토큰이 유효하지 않습니다. GITHUB_TOKEN(PAT)을 재발급하고 만료 여부를 확인하세요."
    elif resp.status_code == 403:
        guide = "권한이 부족합니다. 토큰에 Issues(write) 또는 repo 권한이 필요합니다."
    elif resp.status_code == 404:
        guide = f"리포를 찾지 못했습니다. repo={repo} 설정과 토큰 접근 권한을 확인하세요."
    elif resp.status_code == 422:
        guide = "중복/검증 실패일 수 있습니다. 제목/본문/라벨 값을 확인하세요."

    if guide:
        return f"[ERROR] GitHub Issue 생성 실패: status={resp.status_code}, detail={detail}. 가이드: {guide}"

    return f"[ERROR] GitHub Issue 생성 실패: status={resp.status_code}, detail={detail}"


def trigger_content_crawler_workflow(target_url: str) -> str:
    token = (get_shared_secret("GITHUB_TOKEN") or "").strip()
    repo = _resolve_github_repo()
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
