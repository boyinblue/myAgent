from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3


def backup_sqlite_db(
    src_path: Path,
    backup_dir: Path,
    keep_latest: int = 10,
) -> Path:
    if not src_path.is_file():
        raise FileNotFoundError(f"원본 DB 파일을 찾을 수 없습니다: {src_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = backup_dir / f"{src_path.stem}_{timestamp}{src_path.suffix}"

    src_conn = sqlite3.connect(str(src_path))
    dest_conn = sqlite3.connect(str(dest_path))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    if keep_latest > 0:
        backups = sorted(
            backup_dir.glob(f"{src_path.stem}_*{src_path.suffix}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_file in backups[keep_latest:]:
            old_file.unlink(missing_ok=True)

    return dest_path


def find_project_root(start_file: Path, target_rel: Path) -> Path:
    for candidate in [start_file.resolve().parent, *start_file.resolve().parents]:
        if (candidate / target_rel).is_file():
            return candidate
    # 못 찾으면 기존 기준(스크립트 위치의 2단계 상위 또는 부모)으로 폴백
    parents = list(start_file.resolve().parents)
    return parents[1] if len(parents) > 1 else start_file.resolve().parent


def main() -> None:
    script_path = Path(__file__).resolve()
    rel_db = Path("archive") / "archive_index.db"
    project_root = find_project_root(script_path, rel_db)

    parser = argparse.ArgumentParser(description="SQLite DB 안전 백업 스크립트")
    parser.add_argument(
        "--src",
        type=Path,
        default=project_root / rel_db,
        help="원본 SQLite DB 경로",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=project_root / "backups",
        help="백업 저장 폴더 경로",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="보관할 최신 백업 파일 수 (0이면 무제한)",
    )
    args = parser.parse_args()


if __name__ == "__main__":
    main()