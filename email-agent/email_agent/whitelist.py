import json
from pathlib import Path
from typing import Set


class Whitelist:
    """화이트리스트 관리 클래스 - JSON 파일로 발신자 이메일 저장"""

    def __init__(self, filepath: Path = None):
        if filepath is None:
            filepath = Path(__file__).resolve().parents[1] / "whitelist.json"
        self.filepath = filepath
        self._emails: Set[str] = set()
        self.load()

    def load(self):
        """파일에서 화이트리스트 로드"""
        if not self.filepath.exists():
            self._emails = set()
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._emails = set(data.get("emails", []))
        except Exception:
            self._emails = set()

    def save(self):
        """화이트리스트를 파일에 저장"""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({"emails": sorted(self._emails)}, f, ensure_ascii=False, indent=2)

    def add(self, email: str):
        """화이트리스트에 이메일 추가"""
        email = email.strip().lower()
        if email:
            self._emails.add(email)
            self.save()

    def remove(self, email: str):
        """화이트리스트에서 이메일 제거"""
        email = email.strip().lower()
        if email in self._emails:
            self._emails.discard(email)
            self.save()

    def contains(self, email: str) -> bool:
        """이메일이 화이트리스트에 있는지 확인"""
        return email.strip().lower() in self._emails

    def __contains__(self, email: str) -> bool:
        return self.contains(email)

    def __len__(self) -> int:
        return len(self._emails)

    def list_all(self) -> list:
        """모든 화이트리스트 이메일 반환"""
        return sorted(self._emails)
