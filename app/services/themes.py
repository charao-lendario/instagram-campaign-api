"""Theme classification using keyword matching."""

import re
import unicodedata

from app.core.constants import BIGRAM_TERMS, STOP_WORDS_PT, THEME_KEYWORDS
from app.core.logging import logger
from app.db.pool import get_pool


def _normalize(text: str) -> str:
    """Remove accents and lowercase."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def classify_themes(text: str) -> list[str]:
    """Classify text into theme categories using keyword matching."""
    normalized = _normalize(text)
    found: list[str] = []

    # Check bigrams first
    for bigram in BIGRAM_TERMS:
        if bigram in normalized:
            for theme, keywords in THEME_KEYWORDS.items():
                if bigram in keywords:
                    if theme not in found:
                        found.append(theme)

    # Check unigrams
    words = re.findall(r"\b\w+\b", normalized)
    for word in words:
        if word in STOP_WORDS_PT or len(word) < 3:
            continue
        for theme, keywords in THEME_KEYWORDS.items():
            if word in keywords and theme not in found:
                found.append(theme)

    return found if found else ["outros"]


async def classify_unclassified_comments() -> int:
    """Classify themes for comments that don't have theme entries yet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.id, c.text FROM comments c
               LEFT JOIN themes t ON t.comment_id = c.id
               WHERE t.id IS NULL AND c.text IS NOT NULL AND c.text != ''"""
        )

    if not rows:
        return 0

    count = 0
    async with pool.acquire() as conn:
        for row in rows:
            themes = classify_themes(row["text"])
            for theme in themes:
                try:
                    await conn.execute(
                        """INSERT INTO themes (comment_id, theme, confidence, method)
                           VALUES ($1, $2::theme_category, 1.0, 'keyword'::analysis_method)
                           ON CONFLICT (comment_id, theme, method) DO NOTHING""",
                        row["id"], theme,
                    )
                    count += 1
                except Exception as e:
                    logger.debug(f"Theme insert error: {e}")

    logger.info(f"Classified themes for {count} comment-theme pairs")
    return count


def extract_words_for_wordcloud(
    texts: list[str], max_words: int = 200
) -> list[dict]:
    """Extract word frequencies for wordcloud, filtering stop words."""
    word_freq: dict[str, int] = {}

    for text in texts:
        normalized = _normalize(text)

        # Check bigrams
        for bigram in BIGRAM_TERMS:
            occurrences = normalized.count(bigram)
            if occurrences > 0:
                word_freq[bigram] = word_freq.get(bigram, 0) + occurrences

        # Unigrams
        words = re.findall(r"\b\w+\b", normalized)
        for word in words:
            if word in STOP_WORDS_PT or len(word) < 3:
                continue
            # Skip if part of a counted bigram
            skip = False
            for bigram in BIGRAM_TERMS:
                if word in bigram.split() and bigram in normalized:
                    skip = True
                    break
            if not skip:
                word_freq[word] = word_freq.get(word, 0) + 1

    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [{"word": w, "count": c} for w, c in sorted_words[:max_words]]
