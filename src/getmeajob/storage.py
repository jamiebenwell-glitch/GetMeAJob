from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import os
import sqlite3
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent.parent / "data"
DB_PATH = Path(os.getenv("GETMEAJOB_DB_PATH", str(DATA_DIR / "app.db")))


def _connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                picture TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS document_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS document_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(draft_id) REFERENCES document_drafts(id)
            );

            CREATE TABLE IF NOT EXISTS review_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_title TEXT NOT NULL,
                job_url TEXT NOT NULL DEFAULT '',
                score_total INTEGER NOT NULL,
                score_relevance INTEGER NOT NULL,
                score_tailoring INTEGER NOT NULL,
                score_specificity INTEGER NOT NULL,
                score_structure INTEGER NOT NULL,
                score_clarity INTEGER NOT NULL,
                cv_draft_id INTEGER,
                cover_draft_id INTEGER,
                cv_title TEXT NOT NULL DEFAULT '',
                cover_title TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(cv_draft_id) REFERENCES document_drafts(id),
                FOREIGN KEY(cover_draft_id) REFERENCES document_drafts(id)
            );
            """
        )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def upsert_user(google_sub: str, email: str, name: str, picture: str = "") -> dict[str, Any]:
    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO users (google_sub, email, name, picture)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(google_sub) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                picture = excluded.picture,
                updated_at = CURRENT_TIMESTAMP
            """,
            (google_sub, email, name, picture),
        )
        row = connection.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
    return _row_to_dict(row) or {}


def get_user(user_id: int) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_dict(row)


def list_drafts(user_id: int, kind: str | None = None) -> list[dict[str, Any]]:
    with _connection() as connection:
        if kind:
            rows = connection.execute(
                """
                SELECT * FROM document_drafts
                WHERE user_id = ? AND kind = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (user_id, kind),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM document_drafts
                WHERE user_id = ?
                ORDER BY kind ASC, updated_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_draft(user_id: int, draft_id: int) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM document_drafts WHERE id = ? AND user_id = ?",
            (draft_id, user_id),
        ).fetchone()
    return _row_to_dict(row)


def save_draft(user_id: int, kind: str, title: str, content: str, draft_id: int | None = None) -> dict[str, Any]:
    cleaned_title = title.strip() or f"Untitled {kind.replace('_', ' ')} draft"
    cleaned_content = content.strip()
    with _connection() as connection:
        if draft_id:
            existing = connection.execute(
                "SELECT * FROM document_drafts WHERE id = ? AND user_id = ? AND kind = ?",
                (draft_id, user_id, kind),
            ).fetchone()
            if existing is None:
                raise ValueError("Draft not found.")
            connection.execute(
                """
                UPDATE document_drafts
                SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (cleaned_title, cleaned_content, draft_id),
            )
            if existing["content"] != cleaned_content:
                connection.execute(
                    "INSERT INTO document_revisions (draft_id, content) VALUES (?, ?)",
                    (draft_id, cleaned_content),
                )
            row = connection.execute("SELECT * FROM document_drafts WHERE id = ?", (draft_id,)).fetchone()
        else:
            cursor = connection.execute(
                """
                INSERT INTO document_drafts (user_id, kind, title, content)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, kind, cleaned_title, cleaned_content),
            )
            new_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO document_revisions (draft_id, content) VALUES (?, ?)",
                (new_id, cleaned_content),
            )
            row = connection.execute("SELECT * FROM document_drafts WHERE id = ?", (new_id,)).fetchone()
    return _row_to_dict(row) or {}


def list_revisions(user_id: int, draft_id: int) -> list[dict[str, Any]]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT id FROM document_drafts WHERE id = ? AND user_id = ?",
            (draft_id, user_id),
        ).fetchone()
        if row is None:
            return []
        rows = connection.execute(
            """
            SELECT id, draft_id, content, created_at
            FROM document_revisions
            WHERE draft_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (draft_id,),
        ).fetchall()
    return [dict(item) for item in rows]


def get_revision(user_id: int, draft_id: int, revision_id: int) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT revision.id, revision.draft_id, revision.content, revision.created_at
            FROM document_revisions AS revision
            JOIN document_drafts AS draft ON draft.id = revision.draft_id
            WHERE draft.user_id = ? AND draft.id = ? AND revision.id = ?
            """,
            (user_id, draft_id, revision_id),
        ).fetchone()
    return _row_to_dict(row)


def create_review_run(
    user_id: int,
    job_title: str,
    job_url: str,
    score: dict[str, int],
    cv_draft_id: int | None,
    cover_draft_id: int | None,
    cv_title: str,
    cover_title: str,
) -> dict[str, Any]:
    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO review_runs (
                user_id,
                job_title,
                job_url,
                score_total,
                score_relevance,
                score_tailoring,
                score_specificity,
                score_structure,
                score_clarity,
                cv_draft_id,
                cover_draft_id,
                cv_title,
                cover_title
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                job_title.strip() or "Untitled role",
                job_url.strip(),
                score["total"],
                score["relevance"],
                score["tailoring"],
                score["specificity"],
                score["structure"],
                score["clarity"],
                cv_draft_id,
                cover_draft_id,
                cv_title.strip(),
                cover_title.strip(),
            ),
        )
        row = connection.execute("SELECT * FROM review_runs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_dict(row) or {}


def list_review_history(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM review_runs
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    history = [dict(row) for row in rows]
    previous_score: int | None = None
    for item in history:
        current_score = int(item["score_total"])
        item["score_delta"] = None if previous_score is None else current_score - previous_score
        previous_score = current_score
    return history


def latest_draft_by_kind(user_id: int) -> dict[str, dict[str, Any]]:
    drafts = list_drafts(user_id)
    latest: dict[str, dict[str, Any]] = {}
    for draft in drafts:
        latest.setdefault(draft["kind"], draft)
    return latest


def group_drafts(drafts: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"cv": [], "cover_letter": []}
    for draft in drafts:
        grouped.setdefault(str(draft["kind"]), []).append(draft)
    return grouped
