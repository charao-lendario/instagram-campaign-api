"""Sentiment analysis service: VADER primary + LLM fallback.

Story 1.4: VADER-based sentiment analysis with batch processing.
Story 1.5: LLM fallback for ambiguous comments using OpenAI-compatible API.

Uses ``vaderSentiment`` for fast, free baseline classification, then
``httpx`` async calls to an LLM for reclassifying ambiguous cases
(compound between -0.05 and 0.05, text > 20 chars).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import settings
from app.core.constants import (
    LLM_AMBIGUOUS_MIN_LENGTH,
    LLM_CONFIDENCE_THRESHOLD,
    VADER_NEGATIVE_THRESHOLD,
    VADER_POSITIVE_THRESHOLD,
)
from app.db.supabase import get_supabase
from app.models.enums import SentimentLabel
from app.models.sentiment import (
    LLMSentimentResult,
    SentimentResult,
    SentimentScoreCreate,
)

logger = logging.getLogger(__name__)

# Module-level singleton to avoid reinitializing on every call (~1ms/comment)
_analyzer = SentimentIntensityAnalyzer()

# Prompt structure from architecture.md Section 6.3
SENTIMENT_SYSTEM_PROMPT = (
    "Voce e um analista de sentimento para comentarios em portugues do Instagram. "
    'Classifique o comentario como \'positive\', \'negative\' ou \'neutral\'. '
    'Responda APENAS em JSON: {"label": "positive|negative|neutral", "confidence": 0.0-1.0}'
)


# ---------------------------------------------------------------------------
# Story 1.4: VADER Analysis
# ---------------------------------------------------------------------------


def analyze_sentiment_vader(comment_text: str) -> dict[str, Any]:
    """Classify a single comment using VADER.

    Returns a dict with vader_compound, vader_positive, vader_negative,
    vader_neutral, and vader_label.  The label is determined by the
    compound score thresholds defined in ``constants.py``.

    AC1 / AC2: Threshold boundary logic:
      - compound >= 0.05  -> positive
      - compound <= -0.05 -> negative
      - otherwise         -> neutral
    """
    scores = _analyzer.polarity_scores(comment_text)
    compound = scores["compound"]

    if compound >= VADER_POSITIVE_THRESHOLD:
        label = SentimentLabel.positive
    elif compound <= VADER_NEGATIVE_THRESHOLD:
        label = SentimentLabel.negative
    else:
        label = SentimentLabel.neutral

    return {
        "vader_compound": compound,
        "vader_positive": scores["pos"],
        "vader_negative": scores["neg"],
        "vader_neutral": scores["neu"],
        "vader_label": label.value,
    }


def _get_unanalyzed_comments() -> list[dict[str, Any]]:
    """Fetch comments that do NOT yet have a sentiment_scores record.

    Uses a two-step approach: fetch all comment IDs that already have
    sentiment_scores, then select comments not in that set.
    """
    client = get_supabase()

    # Get IDs of already-analyzed comments
    analyzed_result = (
        client.table("sentiment_scores")
        .select("comment_id")
        .execute()
    )
    analyzed_ids: set[str] = {
        row["comment_id"] for row in (analyzed_result.data or [])
    }

    # Get all comments
    comments_result = (
        client.table("comments")
        .select("id, text")
        .execute()
    )
    all_comments: list[dict[str, Any]] = comments_result.data or []

    # Filter out already analyzed
    unanalyzed = [
        c for c in all_comments if c["id"] not in analyzed_ids
    ]

    return unanalyzed


def analyze_comments_batch(
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run VADER analysis on a batch of comments and persist results.

    AC3: Each comment is analyzed, a sentiment_scores record is created
    with vader_* fields populated and final_label = vader_label.
    LLM fields remain NULL.

    AC4: Comments that already have a sentiment_scores record are NOT
    passed to this function -- the caller (_get_unanalyzed_comments)
    handles deduplication.

    Parameters
    ----------
    comments:
        List of dicts with at least ``id`` and ``text`` keys.

    Returns
    -------
    List of inserted sentiment_score dicts.
    """
    if not comments:
        return []

    client = get_supabase()
    results: list[dict[str, Any]] = []

    for comment in comments:
        comment_id = comment["id"]
        text = comment.get("text", "")

        vader_result = analyze_sentiment_vader(text)

        score_data = SentimentScoreCreate(
            comment_id=UUID(comment_id) if isinstance(comment_id, str) else comment_id,
            vader_compound=vader_result["vader_compound"],
            vader_positive=vader_result["vader_positive"],
            vader_negative=vader_result["vader_negative"],
            vader_neutral=vader_result["vader_neutral"],
            vader_label=SentimentLabel(vader_result["vader_label"]),
            final_label=SentimentLabel(vader_result["vader_label"]),
            llm_label=None,
            llm_confidence=None,
            llm_model=None,
        )

        try:
            insert_result = (
                client.table("sentiment_scores")
                .insert(score_data.model_dump(mode="json"))
                .execute()
            )
            if insert_result.data:
                results.append(insert_result.data[0])
        except Exception as exc:
            # UNIQUE constraint violation or other DB error -- skip
            logger.warning(
                "sentiment_insert_failed",
                extra={
                    "comment_id": str(comment_id),
                    "error_message": str(exc),
                },
            )

    logger.info(
        "analyze_comments_batch_completed",
        extra={
            "total_input": len(comments),
            "total_inserted": len(results),
        },
    )

    return results


def run_vader_analysis() -> dict[str, int]:
    """Orchestrate full VADER batch analysis for all unanalyzed comments.

    AC5: Called by POST /api/v1/analysis/sentiment.
    Returns dict with analyzed_count and skipped_count.
    """
    # Fetch all comments
    client = get_supabase()
    all_comments_result = (
        client.table("comments")
        .select("id, text")
        .execute()
    )
    total_comments = len(all_comments_result.data or [])

    # Fetch unanalyzed subset
    unanalyzed = _get_unanalyzed_comments()
    skipped_count = total_comments - len(unanalyzed)

    # Run batch analysis
    inserted = analyze_comments_batch(unanalyzed)

    logger.info(
        "run_vader_analysis_completed",
        extra={
            "analyzed_count": len(inserted),
            "skipped_count": skipped_count,
        },
    )

    return {
        "analyzed_count": len(inserted),
        "skipped_count": skipped_count,
    }


def get_sentiment_summary(candidate_id: str) -> dict[str, Any]:
    """Aggregate sentiment counts for a candidate.

    AC6: JOIN path: sentiment_scores -> comments -> posts -> candidates.
    Returns overview with counts and average compound score.
    """
    client = get_supabase()

    # Get candidate info
    candidate_result = (
        client.table("candidates")
        .select("id, username")
        .eq("id", candidate_id)
        .limit(1)
        .execute()
    )
    if not candidate_result.data:
        return {
            "candidate_id": candidate_id,
            "candidate_username": "",
            "total_comments": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "average_compound_score": 0.0,
        }

    candidate = candidate_result.data[0]

    # Get posts for this candidate
    posts_result = (
        client.table("posts")
        .select("id")
        .eq("candidate_id", candidate_id)
        .execute()
    )
    post_ids = [p["id"] for p in (posts_result.data or [])]

    if not post_ids:
        return {
            "candidate_id": candidate_id,
            "candidate_username": candidate["username"],
            "total_comments": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "average_compound_score": 0.0,
        }

    # Get comments for those posts
    comments_result = (
        client.table("comments")
        .select("id")
        .in_("post_id", post_ids)
        .execute()
    )
    comment_ids = [c["id"] for c in (comments_result.data or [])]

    if not comment_ids:
        return {
            "candidate_id": candidate_id,
            "candidate_username": candidate["username"],
            "total_comments": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "average_compound_score": 0.0,
        }

    # Get sentiment scores for those comments
    sentiment_result = (
        client.table("sentiment_scores")
        .select("final_label, vader_compound")
        .in_("comment_id", comment_ids)
        .execute()
    )
    scores = sentiment_result.data or []

    positive_count = sum(1 for s in scores if s["final_label"] == "positive")
    negative_count = sum(1 for s in scores if s["final_label"] == "negative")
    neutral_count = sum(1 for s in scores if s["final_label"] == "neutral")
    total = len(scores)

    avg_compound = 0.0
    if total > 0:
        avg_compound = round(
            sum(s["vader_compound"] for s in scores) / total,
            4,
        )

    return {
        "candidate_id": candidate_id,
        "candidate_username": candidate["username"],
        "total_comments": total,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "average_compound_score": avg_compound,
    }


# ---------------------------------------------------------------------------
# Story 1.5: LLM Fallback
# ---------------------------------------------------------------------------


async def analyze_sentiment_llm(comment_text: str) -> dict[str, Any]:
    """Classify a single comment via LLM (OpenAI-compatible API).

    AC1 (1.5): Sends the Portuguese prompt defined in architecture.md
    Section 6.3, parses the JSON response, returns llm_label,
    llm_confidence, and llm_model.

    AC2 (1.5): Prompt structure matches exactly:
      - System: Portuguese analyst instruction
      - User: "Classifique o sentimento: \"{comment_text}\""
      - temperature: 0.1, max_tokens: 50
    """
    api_url = "https://api.openai.com/v1/chat/completions"
    if settings.LLM_PROVIDER != "openai":
        # Allow custom base URL for non-OpenAI providers
        api_url = f"https://api.{settings.LLM_PROVIDER}.com/v1/chat/completions"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SENTIMENT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f'Classifique o sentimento: "{comment_text}"',
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 50,
            },
        )
        response.raise_for_status()
        data = response.json()
        content_str = data["choices"][0]["message"]["content"]
        content = json.loads(content_str)

        # Validate label is one of the expected values
        label = content.get("label", "neutral")
        if label not in ("positive", "negative", "neutral"):
            label = "neutral"

        confidence = float(content.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        return {
            "llm_label": label,
            "llm_confidence": confidence,
            "llm_model": settings.LLM_MODEL,
        }


def _get_ambiguous_comments() -> list[dict[str, Any]]:
    """Fetch comments in the ambiguous zone eligible for LLM reclassification.

    AC3 (1.5): Criteria:
      - vader_compound > -0.05 AND vader_compound < 0.05
      - llm_label IS NULL
      - comment text length > LLM_AMBIGUOUS_MIN_LENGTH (20 chars)

    Returns list of dicts with comment_id, text, vader_compound, vader_label.
    """
    client = get_supabase()

    # Get ambiguous sentiment scores (compound strictly between thresholds, no LLM yet)
    sentiment_result = (
        client.table("sentiment_scores")
        .select("comment_id, vader_compound, vader_label")
        .gt("vader_compound", VADER_NEGATIVE_THRESHOLD)
        .lt("vader_compound", VADER_POSITIVE_THRESHOLD)
        .is_("llm_label", "null")
        .execute()
    )
    ambiguous_scores = sentiment_result.data or []

    if not ambiguous_scores:
        return []

    # Get the actual comment texts
    comment_ids = [s["comment_id"] for s in ambiguous_scores]
    comments_result = (
        client.table("comments")
        .select("id, text")
        .in_("id", comment_ids)
        .execute()
    )
    comments_by_id: dict[str, str] = {
        c["id"]: c["text"] for c in (comments_result.data or [])
    }

    # Combine and filter by minimum text length
    eligible: list[dict[str, Any]] = []
    for score in ambiguous_scores:
        cid = score["comment_id"]
        text = comments_by_id.get(cid, "")
        if len(text) > LLM_AMBIGUOUS_MIN_LENGTH:
            eligible.append({
                "comment_id": cid,
                "text": text,
                "vader_compound": score["vader_compound"],
                "vader_label": score["vader_label"],
            })

    return eligible


async def reclassify_ambiguous_comments() -> dict[str, int]:
    """Reclassify ambiguous comments using LLM fallback.

    AC3 (1.5): Selects ambiguous comments, calls LLM for each.
    AC4 (1.5): Updates sentiment_scores based on confidence threshold:
      - confidence >= 0.7: final_label = llm_label
      - confidence < 0.7:  final_label remains vader_label
      - Both: llm_label, llm_confidence, llm_model are persisted.
    AC5 (1.5): On API failure, error is logged, record is NOT modified,
      processing continues to next comment.
    AC6 (1.5): Returns reclassified_count, api_calls_made,
      confidence_upgrades, retained_vader_label.
    AC7 (1.5): Logs structured cost estimate.

    Returns dict with reclassification statistics.
    """
    ambiguous = _get_ambiguous_comments()

    api_calls_made = 0
    confidence_upgrades = 0
    retained_vader_label = 0
    reclassified_count = 0

    client = get_supabase()

    for item in ambiguous:
        comment_id = item["comment_id"]
        text = item["text"]
        vader_label = item["vader_label"]

        try:
            llm_result = await analyze_sentiment_llm(text)
            api_calls_made += 1

            llm_label = llm_result["llm_label"]
            llm_confidence = llm_result["llm_confidence"]
            llm_model = llm_result["llm_model"]

            # AC4: Determine final_label based on confidence threshold
            if llm_confidence >= LLM_CONFIDENCE_THRESHOLD:
                final_label = llm_label
                confidence_upgrades += 1
            else:
                final_label = vader_label
                retained_vader_label += 1

            # Update sentiment_scores record
            client.table("sentiment_scores").update({
                "llm_label": llm_label,
                "llm_confidence": llm_confidence,
                "llm_model": llm_model,
                "final_label": final_label,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("comment_id", str(comment_id)).execute()

            reclassified_count += 1

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
            # AC5: Log error, do NOT modify sentiment_scores, continue
            logger.error(
                "llm_reclassification_failed",
                extra={
                    "comment_id": str(comment_id),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            continue
        except Exception as exc:
            # Catch any unexpected errors to not break the batch
            logger.error(
                "llm_reclassification_unexpected_error",
                extra={
                    "comment_id": str(comment_id),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            continue

    # AC7: Structured cost log
    # GPT-4o-mini: ~30 tokens input + 20 tokens output per comment
    # ~$0.00015/1K input + $0.0006/1K output
    estimated_input_tokens = api_calls_made * 30
    estimated_output_tokens = api_calls_made * 20
    cost_estimate_usd = round(
        (estimated_input_tokens / 1000 * 0.00015)
        + (estimated_output_tokens / 1000 * 0.0006),
        6,
    )

    logger.info(
        "reclassify_ambiguous_completed",
        extra={
            "api_calls_made": api_calls_made,
            "reclassified_count": reclassified_count,
            "confidence_upgrades": confidence_upgrades,
            "retained_vader_label": retained_vader_label,
            "cost_estimate_usd": cost_estimate_usd,
        },
    )

    return {
        "reclassified_count": reclassified_count,
        "api_calls_made": api_calls_made,
        "confidence_upgrades": confidence_upgrades,
        "retained_vader_label": retained_vader_label,
    }


# ---------------------------------------------------------------------------
# Contextual Sentiment Analysis (post caption + comments)
# ---------------------------------------------------------------------------

CONTEXTUAL_SYSTEM_PROMPT = """\
Você é um analista de sentimento político especializado em campanhas eleitorais brasileiras.

TAREFA: Analisar comentários de um post do Instagram considerando o CONTEXTO do post.

IMPORTANTE: Muitos candidatos postam conteúdo polêmico (denúncias, críticas sociais, temas revoltantes).
Quando o público reage com revolta ao TEMA do post (ex: "que nojo!", "isso é absurdo!"), isso geralmente
é APOIO à candidata por denunciar/expor o problema — NÃO é ataque à candidata.

CLASSIFIQUE cada comentário em:
- "apoio": O comentário APOIA a candidata (inclui revolta com o tema que demonstra concordância)
- "contra": O comentário ATACA ou CRITICA a candidata diretamente
- "neutro": Não é possível determinar, ou é comentário genérico (emoji, marcação de amigo, etc.)

Responda APENAS em JSON:
{"results": [{"index": 0, "classificacao": "apoio|contra|neutro"}, ...]}
"""


async def analyze_post_contextual_sentiment(post_id: str) -> dict:
    """Analyze all comments of a post with contextual awareness.

    Sends post caption + all comments to LLM in a single call.
    Returns breakdown of apoio/contra/neutro.
    """
    client = get_supabase()

    # Get post data
    post_result = (
        client.table("posts")
        .select("id, caption, candidate_id")
        .eq("id", post_id)
        .execute()
    )
    if not post_result.data:
        return {"error": "Post não encontrado"}

    post = post_result.data[0]
    caption = post.get("caption") or ""

    # Get candidate info
    cand_result = (
        client.table("candidates")
        .select("display_name")
        .eq("id", post["candidate_id"])
        .execute()
    )
    candidate_name = cand_result.data[0]["display_name"] if cand_result.data else "candidata"

    # Get all comments for this post
    comments_result = (
        client.table("comments")
        .select("id, text")
        .eq("post_id", post_id)
        .execute()
    )
    comments = comments_result.data or []

    if not comments:
        return {
            "post_id": post_id,
            "caption_preview": caption[:100],
            "total_comments": 0,
            "apoio": 0,
            "contra": 0,
            "neutro": 0,
            "apoio_percent": 0,
            "contra_percent": 0,
        }

    # Build user message with caption + all comments
    comment_lines = []
    for i, c in enumerate(comments):
        text = (c.get("text") or "").replace("\n", " ").strip()
        if text:
            comment_lines.append(f"{i}. {text}")

    user_message = (
        f"CANDIDATA: {candidate_name}\n\n"
        f"LEGENDA DO POST:\n{caption[:500]}\n\n"
        f"COMENTÁRIOS ({len(comment_lines)}):\n"
        + "\n".join(comment_lines)
    )

    api_url = "https://api.openai.com/v1/chat/completions"
    if settings.LLM_PROVIDER != "openai":
        api_url = f"https://api.{settings.LLM_PROVIDER}.com/v1/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            response = await http_client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": CONTEXTUAL_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()
            data = response.json()
            content_str = data["choices"][0]["message"]["content"]

            clean_content = content_str.strip()
            if clean_content.startswith("```"):
                lines = clean_content.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                clean_content = "\n".join(lines)

            parsed = json.loads(clean_content)
            results = parsed.get("results", [])

            apoio = sum(1 for r in results if r.get("classificacao") == "apoio")
            contra = sum(1 for r in results if r.get("classificacao") == "contra")
            neutro = sum(1 for r in results if r.get("classificacao") == "neutro")
            total = apoio + contra + neutro or 1

            return {
                "post_id": post_id,
                "caption_preview": caption[:100],
                "candidate_name": candidate_name,
                "total_comments": len(comments),
                "total_classified": len(results),
                "apoio": apoio,
                "contra": contra,
                "neutro": neutro,
                "apoio_percent": round((apoio / total) * 100, 1),
                "contra_percent": round((contra / total) * 100, 1),
                "neutro_percent": round((neutro / total) * 100, 1),
            }

    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error(
            "contextual_sentiment_failed",
            extra={
                "post_id": post_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        return {"error": f"Falha na análise: {type(exc).__name__}: {exc}"}
