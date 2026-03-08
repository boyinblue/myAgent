from urllib.parse import quote

import requests

from .models import UnsubscribeAction


def execute_action(action: UnsubscribeAction, dry_run: bool = True, timeout: int = 10) -> str:
    if dry_run:
        return f"[DRY-RUN] {action.kind}: {action.value}"

    if action.kind == "mailto":
        target = action.value[len("mailto:"):]
        if "?" not in target:
            target = f"{target}?subject={quote('unsubscribe')}&body={quote('Please unsubscribe this email address.') }"
        return f"mailto://{target}"

    response = requests.get(action.value, timeout=timeout, allow_redirects=True)
    return f"HTTP {response.status_code}: {response.url}"
