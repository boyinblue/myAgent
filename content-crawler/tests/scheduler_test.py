import sqlite3

import pytest

import run_anniversary_digest
from scheduler import AnniversaryFinder


def test_find_anniversary_posts_returns_empty_for_valid_empty_database(tmp_path):
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    database_path = archive_root / "archive_index.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE posts (
                title TEXT, url TEXT, created_at TEXT,
                published_date TEXT, is_hidden INTEGER
            )
            """
        )

    assert AnniversaryFinder(str(archive_root)).find_anniversary_posts() == []


def test_find_anniversary_posts_raises_for_invalid_database(tmp_path):
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    (archive_root / "archive_index.db").write_text("not a sqlite database")

    with pytest.raises(RuntimeError, match="아카이브 DB 조회 실패"):
        AnniversaryFinder(str(archive_root)).find_anniversary_posts()


def test_find_random_posts_returns_three_visible_posts_and_excludes_urls(tmp_path):
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    database_path = archive_root / "archive_index.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE posts (
                title TEXT, url TEXT, created_at TEXT,
                platform TEXT, published_date TEXT, is_hidden INTEGER
            )
            """
        )
        connection.executemany(
            "INSERT INTO posts (title, url, is_hidden) VALUES (?, ?, ?)",
            [(f"Post {i}", f"https://example.com/{i}", 0) for i in range(12)]
            + [("Hidden post", "https://example.com/hidden", 1)],
        )

    finder = AnniversaryFinder(str(archive_root))
    posts = finder.find_random_posts(exclude_urls=["https://example.com/0"])

    assert len(posts) == 3
    assert all(post["url"] != "https://example.com/0" for post in posts)
    assert all(post["url"] != "https://example.com/hidden" for post in posts)


def test_format_daily_digest_includes_random_posts_when_no_anniversaries():
    finder = AnniversaryFinder()

    messages = finder.format_daily_digest(
        [],
        [
            {
                "title": "A <safe> title",
                "url": "https://example.com/post",
                "platform": "Tistory",
                "published_date": "2024-01-02",
            }
        ],
    )

    assert messages[0] == "오늘의 기념일 포스트가 없습니다."
    assert messages[1] == "<b>🎲 랜덤 포스트 추천 (1개)</b>"
    assert messages[2] == (
        "1. [Tistory] A &lt;safe&gt; title\n"
        "   📅 2024-01-02\n"
        "   🔗 https://example.com/post"
    )


def test_digest_exits_with_failure_when_telegram_send_fails(monkeypatch, tmp_path):
    database_path = tmp_path / "archive_index.db"
    database_path.touch()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    class EmptyFinder:
        db_file = str(database_path)

        def __init__(self, archive_root):
            pass

        def find_anniversary_posts(self, years_back):
            return []

        def find_random_posts(self, count, exclude_urls=None):
            return []

        def format_daily_digest(self, anniversary_posts, random_posts):
            return ["No anniversary posts"]

    class FailedNotifier:
        def __init__(self, token):
            pass

        def send_digest(self, title, messages):
            return False

    monkeypatch.setattr(run_anniversary_digest, "AnniversaryFinder", EmptyFinder)
    monkeypatch.setattr(run_anniversary_digest, "TelegramNotifier", FailedNotifier)

    with pytest.raises(SystemExit) as error:
        run_anniversary_digest.main()

    assert error.value.code == 1


def test_send_digest_disables_link_previews(monkeypatch):
    from utils.telegram_notifier import TelegramNotifier

    calls = {}

    class SuccessfulResponse:
        ok = True

        def json(self):
            return {"ok": True}

    def fake_post(url, json, **kwargs):
        calls["url"] = url
        calls["payload"] = json
        return SuccessfulResponse()

    monkeypatch.setattr("utils.telegram_notifier.requests.post", fake_post)
    notifier = TelegramNotifier(token="test-token", chat_id="123")

    assert notifier.send_digest(
        "Daily Digest",
        [
            "1. [Tistory] A &lt;safe&gt; title\n"
            "   🔗 https://example.com/post?a=1&amp;b=2"
        ],
    )
    assert calls["url"].endswith("/sendMessage")
    assert calls["payload"]["link_preview_options"] == {"is_disabled": True}
    assert "A &lt;safe&gt; title" in calls["payload"]["text"]
    assert "https://example.com/post?a=1&amp;b=2" in calls["payload"]["text"]


def test_digest_sends_random_posts_as_a_single_message(monkeypatch, tmp_path):
    database_path = tmp_path / "archive_index.db"
    database_path.touch()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    posts = [
        {
            "title": f"Post {index}",
            "url": f"https://example.com/{index}",
            "published_date": "2026-01-02",
            "images": None,
        }
        for index in range(6)
    ]

    class FinderWithPosts:
        db_file = str(database_path)

        def __init__(self, archive_root):
            pass

        def find_anniversary_posts(self, years_back):
            return []

        def find_random_posts(self, count, exclude_urls=None):
            assert count == 3
            return posts[:count]

        def format_daily_digest(self, anniversary_posts, random_posts):
            return ["No anniversary posts"] + [post["url"] for post in random_posts]

    class CapturingNotifier:
        sent_messages = []

        def __init__(self, token):
            pass

        def send_digest(self, title, messages):
            self.sent_messages.append((title, messages))
            return True

    notifier_class = CapturingNotifier
    notifier_class.sent_messages = []
    monkeypatch.setattr(run_anniversary_digest, "AnniversaryFinder", FinderWithPosts)
    monkeypatch.setattr(run_anniversary_digest, "TelegramNotifier", notifier_class)

    run_anniversary_digest.main()

    assert len(notifier_class.sent_messages) == 1
    assert len(notifier_class.sent_messages[0][1]) == 4
