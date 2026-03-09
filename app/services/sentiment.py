"""Sentiment analysis using VADER and LLM fallback."""

import json
from uuid import UUID

import httpx
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import settings
from app.core.logging import logger
from app.db.pool import get_pool

_analyzer = SentimentIntensityAnalyzer()


def classify_vader(compound: float) -> str:
    """Classify sentiment from VADER compound score."""
    if compound >= 0.05:
        return "positive"
    elif compound <= -0.05:
        return "negative"
    return "neutral"


async def analyze_unanalyzed_comments() -> int:
    """Run VADER sentiment on all comments without sentiment scores. Returns count."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.id, c.text FROM comments c
               LEFT JOIN sentiment_scores s ON s.comment_id = c.id
               WHERE s.id IS NULL AND c.text IS NOT NULL AND c.text != ''"""
        )

    if not rows:
        return 0

    count = 0
    async with pool.acquire() as conn:
        for row in rows:
            text = row["text"]
            scores = _analyzer.polarity_scores(text)
            compound = scores["compound"]
            label = classify_vader(compound)

            await conn.execute(
                """INSERT INTO sentiment_scores
                   (comment_id, vader_compound, vader_positive, vader_negative,
                    vader_neutral, vader_label, final_label)
                   VALUES ($1, $2, $3, $4, $5, $6::sentiment_label, $7::sentiment_label)
                   ON CONFLICT (comment_id) DO NOTHING""",
                row["id"], compound, scores["pos"], scores["neg"],
                scores["neu"], label, label,
            )
            count += 1

    logger.info(f"VADER analyzed {count} comments")
    return count


async def get_sentiment_summary(candidate_id: str | None = None) -> dict:
    """Get sentiment summary, optionally filtered by candidate."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if candidate_id:
            row = await conn.fetchrow(
                """SELECT
                     COUNT(*) as total,
                     COUNT(*) FILTER (WHERE s.final_label = 'positive') as positive,
                     COUNT(*) FILTER (WHERE s.final_label = 'negative') as negative,
                     COUNT(*) FILTER (WHERE s.final_label = 'neutral') as neutral,
                     COALESCE(AVG(s.vader_compound), 0) as avg_compound
                   FROM sentiment_scores s
                   JOIN comments c ON c.id = s.comment_id
                   JOIN posts p ON p.id = c.post_id
                   WHERE p.candidate_id = $1::uuid""",
                candidate_id,
            )
            # Get candidate info
            cand = await conn.fetchrow(
                "SELECT username FROM candidates WHERE id = $1::uuid",
                candidate_id,
            )
        else:
            row = await conn.fetchrow(
                """SELECT
                     COUNT(*) as total,
                     COUNT(*) FILTER (WHERE final_label = 'positive') as positive,
                     COUNT(*) FILTER (WHERE final_label = 'negative') as negative,
                     COUNT(*) FILTER (WHERE final_label = 'neutral') as neutral,
                     COALESCE(AVG(vader_compound), 0) as avg_compound
                   FROM sentiment_scores"""
            )
            cand = None

        return {
            "total_comments": row["total"],
            "distribution": {
                "positive": row["positive"],
                "negative": row["negative"],
                "neutral": row["neutral"],
            },
            "average_compound": round(float(row["avg_compound"]), 4),
            "candidate_id": candidate_id,
            "candidate_username": cand["username"] if cand else None,
        }


async def run_llm_fallback() -> int:
    """Reclassify ambiguous comments (near-zero VADER) using LLM."""
    if not settings.LLM_API_KEY:
        logger.warning("LLM_API_KEY not set, skipping LLM fallback")
        return 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT s.id as score_id, c.text, s.vader_compound
               FROM sentiment_scores s
               JOIN comments c ON c.id = s.comment_id
               WHERE s.llm_label IS NULL
                 AND s.vader_compound > -0.05
                 AND s.vader_compound < 0.05
                 AND LENGTH(c.text) > 20
               LIMIT 50"""
        )

    if not rows:
        return 0

    reclassified = 0
    for row in rows:
        try:
            label, confidence = await _call_llm_sentiment(row["text"])
            if label and confidence >= 0.7:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE sentiment_scores
                           SET llm_label = $1::sentiment_label,
                               llm_confidence = $2,
                               llm_model = $3,
                               final_label = $1::sentiment_label,
                               updated_at = NOW()
                           WHERE id = $4""",
                        label, confidence, settings.LLM_MODEL, row["score_id"],
                    )
                reclassified += 1
        except Exception as e:
            logger.error(f"LLM fallback error: {e}")

    logger.info(f"LLM reclassified {reclassified} comments")
    return reclassified


async def analyze_contextual_sentiment(post_id: str) -> dict:
    """Analyze sentiment for all comments on a specific post with context."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        post = await conn.fetchrow(
            "SELECT id, caption FROM posts WHERE id = $1::uuid", post_id
        )
        if not post:
            raise ValueError(f"Post {post_id} not found")

        comments = await conn.fetch(
            """SELECT c.id, c.text, c.author_username,
                      s.vader_compound, s.final_label
               FROM comments c
               LEFT JOIN sentiment_scores s ON s.comment_id = c.id
               WHERE c.post_id = $1::uuid
               ORDER BY c.commented_at ASC NULLS LAST""",
            post["id"],
        )

    # Get candidate name
    async with pool.acquire() as conn:
        cand_row = await conn.fetchrow(
            """SELECT ca.display_name FROM candidates ca
               JOIN posts p ON p.candidate_id = ca.id
               WHERE p.id = $1::uuid""",
            post_id,
        )

    candidate_name = cand_row["display_name"] if cand_row else "Candidato"

    total = len(comments)
    classified = sum(1 for c in comments if c["final_label"] is not None)
    # Map: positive -> apoio, negative -> contra, neutral -> neutro
    apoio = sum(1 for c in comments if c["final_label"] == "positive")
    contra = sum(1 for c in comments if c["final_label"] == "negative")
    neutro = sum(1 for c in comments if c["final_label"] == "neutral")

    caption_text = post["caption"] or ""
    caption_preview = caption_text[:120] if len(caption_text) > 120 else caption_text

    return {
        "post_id": post_id,
        "caption_preview": caption_preview,
        "candidate_name": candidate_name,
        "total_comments": total,
        "total_classified": classified,
        "apoio": apoio,
        "contra": contra,
        "neutro": neutro,
        "apoio_percent": round(apoio / classified * 100, 1) if classified else 0.0,
        "contra_percent": round(contra / classified * 100, 1) if classified else 0.0,
        "neutro_percent": round(neutro / classified * 100, 1) if classified else 0.0,
    }


async def _call_llm_sentiment(text: str) -> tuple[str | None, float]:
    """Call LLM API to classify sentiment. Returns (label, confidence)."""
    prompt = (
        "Classify the sentiment of this Instagram comment as exactly one of: "
        "positive, negative, neutral.\n"
        "Respond ONLY with a JSON object: {\"label\": \"...\", \"confidence\": 0.0-1.0}\n\n"
        f"Comment: {text}"
    )

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 50,
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Parse JSON response
        result = json.loads(content)
        label = result.get("label", "").lower()
        confidence = float(result.get("confidence", 0.0))

        if label in ("positive", "negative", "neutral"):
            return label, confidence

    return None, 0.0
