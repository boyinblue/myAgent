import email
import re
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr
from typing import List

from .models import MessageRecord, UnsubscribeAction


URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


def decode_mime(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded)


def parse_list_unsubscribe(raw_header: str) -> List[str]:
    if not raw_header:
        return []
    items = []
    for token in raw_header.split(","):
        token = token.strip().strip("<>")
        if token.startswith("http://") or token.startswith("https://") or token.startswith("mailto:"):
            items.append(token)
    return items


def extract_text_links_from_body(msg: Message) -> List[str]:
    links: List[str] = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        for found in URL_RE.findall(text):
            links.append(found.rstrip('.,)\"]'))
    return list(dict.fromkeys(links))


def message_to_record(uid: bytes, raw_message: bytes) -> MessageRecord:
    msg = email.message_from_bytes(raw_message)
    sender_name, sender_email = parseaddr(decode_mime(msg.get("From", "")))
    subject = decode_mime(msg.get("Subject", ""))
    date = msg.get("Date", "")

    list_unsub = parse_list_unsubscribe(decode_mime(msg.get("List-Unsubscribe", "")))
    body_links = extract_text_links_from_body(msg)

    return MessageRecord(
        uid=uid.decode("utf-8", errors="ignore"),
        sender_email=sender_email.lower(),
        sender_name=sender_name,
        subject=subject,
        date=date,
        list_unsubscribe=list_unsub,
        body_links=body_links,
    )


def build_actions(record: MessageRecord) -> List[UnsubscribeAction]:
    actions: List[UnsubscribeAction] = []
    for value in record.list_unsubscribe:
        kind = "mailto" if value.startswith("mailto:") else "http"
        actions.append(UnsubscribeAction(kind=kind, value=value, source="list-unsubscribe"))

    keywords = ("unsubscribe", "optout", "opt-out", "수신거부")
    for url in record.body_links:
        low = url.lower()
        if any(word in low for word in keywords):
            actions.append(UnsubscribeAction(kind="http", value=url, source="body-link"))

    unique = []
    seen = set()
    for action in actions:
        key = (action.kind, action.value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(action)
    return unique
