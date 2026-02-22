"""Theme classification service via keyword matching.

Story 1.6 AC7/AC8: Classify comments into thematic categories using
deterministic keyword matching against THEME_KEYWORDS from constants.py.

Each comment can match multiple themes. Comments with no keyword match
receive the default theme "outros" with confidence 0.5.
"""

from __future__ import annotations

import logging
import unicodedata
from typing import Any
from uuid import UUID

from app.core.constants import THEME_KEYWORDS
from app.db.supabase import get_supabase
from app.models.enums import AnalysisMethod, ThemeCategory
from app.models.theme import ThemeCreate

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Lowercase and strip accents for keyword matching.

    AC7a: text is lowercased and normalized (sem acentos para matching).
    """
    lowered = text.lower()
    # NFD decomposition splits accented chars into base + combining mark
    nfkd = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def classify_comment_themes(
    comment_text: str,
    comment_id: UUID | None = None,
) -> list[ThemeCreate]:
    """Classify a single comment into themes via keyword matching.

    AC7: For each theme in THEME_KEYWORDS, checks if any keyword appears
    in the normalized text. Returns a ThemeCreate per matched theme with
    method="keyword" and confidence=1.0.

    AC7d: If no theme matches, returns [ThemeCreate(theme="outros",
    confidence=0.5, method="keyword")].

    Parameters
    ----------
    comment_text:
        Raw comment text.
    comment_id:
        UUID of the comment (required for ThemeCreate but optional
        here to allow testing without a real ID).

    Returns
    -------
    List of ThemeCreate instances, one per matched theme.
    """
    normalized = _normalize_text(comment_text)
    matched_themes: list[ThemeCreate] = []

    # Use a placeholder UUID when comment_id is not provided (testing)
    cid = comment_id or UUID("00000000-0000-0000-0000-000000000000")

    for theme_name, keywords in THEME_KEYWORDS.items():
        if theme_name == "outros" or not keywords:
            continue
        for keyword in keywords:
            normalized_kw = _normalize_text(keyword)
            if normalized_kw in normalized:
                matched_themes.append(
                    ThemeCreate(
                        comment_id=cid,
                        theme=ThemeCategory(theme_name),
                        confidence=1.0,
                        method=AnalysisMethod.keyword,
                    )
                )
                break  # One match per theme is enough

    if not matched_themes:
        matched_themes.append(
            ThemeCreate(
                comment_id=cid,
                theme=ThemeCategory.outros,
                confidence=0.5,
                method=AnalysisMethod.keyword,
            )
        )

    return matched_themes


def classify_all_unthemed_comments() -> int:
    """Classify all comments that have no theme records yet.

    AC8: Fetches comment_ids without entries in themes, runs
    classify_comment_themes for each, and upserts the results.

    Returns the total number of comments processed.
    """
    client = get_supabase()

    # Get all comment IDs that already have theme records
    themed_result = client.table("themes").select("comment_id").execute()
    themed_ids: set[str] = {
        row["comment_id"] for row in (themed_result.data or [])
    }

    # Get all comments
    comments_result = (
        client.table("comments")
        .select("id, text")
        .execute()
    )
    all_comments: list[dict[str, Any]] = comments_result.data or []

    # Filter to unthemed comments
    unthemed = [c for c in all_comments if c["id"] not in themed_ids]

    if not unthemed:
        logger.info("classify_all_unthemed_comments: no unthemed comments found")
        return 0

    processed = 0
    for comment in unthemed:
        comment_id = UUID(comment["id"])
        text = comment.get("text", "")

        themes = classify_comment_themes(text, comment_id)

        for theme_create in themes:
            try:
                client.table("themes").upsert(
                    theme_create.model_dump(mode="json"),
                    on_conflict="comment_id,theme,method",
                ).execute()
            except Exception as exc:
                logger.warning(
                    "theme_upsert_failed",
                    extra={
                        "comment_id": str(comment_id),
                        "theme": theme_create.theme.value,
                        "error_message": str(exc),
                    },
                )

        processed += 1

    logger.info(
        "classify_all_unthemed_comments_completed",
        extra={"comments_processed": processed},
    )

    return processed
