from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UnsubscribeAction:
    kind: str  # 'http' | 'mailto'
    value: str
    source: str  # 'list-unsubscribe' | 'body-link'


@dataclass
class MessageRecord:
    uid: str
    sender_email: str
    sender_name: str
    subject: str
    date: str
    list_unsubscribe: List[str] = field(default_factory=list)
    body_links: List[str] = field(default_factory=list)


@dataclass
class SenderSummary:
    sender_email: str
    sender_name: str
    count: int
    actions: List[UnsubscribeAction]
    sample_subject: Optional[str] = None
