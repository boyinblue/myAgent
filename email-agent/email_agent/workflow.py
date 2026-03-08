from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .models import MessageRecord, SenderSummary
from .parsing import build_actions


def summarize_by_sender(records: Iterable[MessageRecord], whitelist=None) -> List[SenderSummary]:
    grouped: Dict[str, List[MessageRecord]] = defaultdict(list)
    for rec in records:
        if not rec.sender_email:
            continue
        # 화이트리스트에 있는 발신자는 제외
        if whitelist and rec.sender_email in whitelist:
            continue
        grouped[rec.sender_email].append(rec)

    summaries: List[SenderSummary] = []
    for sender_email, sender_records in grouped.items():
        sender_name = next((r.sender_name for r in sender_records if r.sender_name), "")
        sample_subject = next((r.subject for r in sender_records if r.subject), None)

        actions = []
        for record in sender_records[:10]:
            actions.extend(build_actions(record))

        dedup = []
        seen = set()
        for action in actions:
            key = (action.kind, action.value)
            if key in seen:
                continue
            seen.add(key)
            dedup.append(action)

        summaries.append(
            SenderSummary(
                sender_email=sender_email,
                sender_name=sender_name,
                count=len(sender_records),
                actions=dedup,
                sample_subject=sample_subject,
            )
        )

    return sorted(summaries, key=lambda x: x.count, reverse=True)
