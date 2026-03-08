import imaplib
from typing import List

from .config import Settings
from .models import MessageRecord
from .parsing import message_to_record


class DaumImapClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self):
        self.conn = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port)
        login_candidates = [self.settings.email]
        if "@" in self.settings.email:
            login_candidates.append(self.settings.email.split("@", 1)[0])

        login_error = None
        for login_id in login_candidates:
            try:
                self.conn.login(login_id, self.settings.app_password)
                return self
            except imaplib.IMAP4.error as exc:
                login_error = exc

        raise RuntimeError(
            "IMAP 로그인 실패: DAUM_EMAIL/DAUM_APP_PASSWORD를 확인하세요. "
            f"host={self.settings.imap_host}:{self.settings.imap_port}, "
            f"email={self.settings.email}, error={login_error}"
        )

    def __exit__(self, exc_type, exc, tb):
        if self.conn is not None:
            try:
                self.conn.logout()
            except Exception:
                pass

    def fetch_recent(self, mailbox: str, limit: int = 200) -> List[MessageRecord]:
        if self.conn is None:
            raise RuntimeError("IMAP connection is not initialized")

        status, _ = self.conn.select(mailbox, readonly=True)
        if status != "OK":
            return []

        status, data = self.conn.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []

        uids = data[0].split()
        target = uids[-limit:]
        records: List[MessageRecord] = []

        for uid in target:
            status, fetched = self.conn.fetch(uid, "(RFC822)")
            if status != "OK" or not fetched or fetched[0] is None:
                continue
            raw = fetched[0][1]
            if not raw:
                continue
            try:
                records.append(message_to_record(uid, raw))
            except Exception:
                continue

        return records
