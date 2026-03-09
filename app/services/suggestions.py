"""Strategic suggestions generation using LLM."""

import json
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.db.pool import get_pool


async def generate_suggestions() -> dict:
    """Generate strategic suggestions based on current analytics data."""
    pool = await get_pool()

    # Gather data snapshot
    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """SELECT
                 c.id, c.username, c.display_name,
                 COUNT(DISTINCT p.id) as total_posts,
                 COUNT(DISTINCT cm.id) as total_comments,
                 COALESCE(AVG(s.vader_compound), 0) as avg_sentiment,
                 COUNT(*) FILTER (WHERE s.final_label = 'positive') as positive,
                 COUNT(*) FILTER (WHERE s.final_label = 'negative') as negative,
                 COUNT(*) FILTER (WHERE s.final_label = 'neutral') as neutral
               FROM candidates c
               LEFT JOIN posts p ON p.candidate_id = c.id
               LEFT JOIN comments cm ON cm.post_id = p.id
               LEFT JOIN sentiment_scores s ON s.comment_id = cm.id
               WHERE c.is_active = TRUE AND COALESCE(c.is_competitor, FALSE) = FALSE
               GROUP BY c.id, c.username, c.display_name"""
        )

        # Top themes per candidate
        themes_data = {}
        for cand in candidates:
            themes = await conn.fetch(
                """SELECT t.theme, COUNT(*) as cnt
                   FROM themes t
                   JOIN comments cm ON cm.id = t.comment_id
                   JOIN posts p ON p.id = cm.post_id
                   WHERE p.candidate_id = $1
                   GROUP BY t.theme ORDER BY cnt DESC LIMIT 5""",
                cand["id"],
            )
            themes_data[cand["username"]] = [
                {"theme": t["theme"], "count": t["cnt"]} for t in themes
            ]

        # Top negative comments
        neg_comments = await conn.fetch(
            """SELECT c.text, s.vader_compound, p.url, cand.username
               FROM comments c
               JOIN sentiment_scores s ON s.comment_id = c.id
               JOIN posts p ON p.id = c.post_id
               JOIN candidates cand ON cand.id = p.candidate_id
               WHERE s.final_label = 'negative'
               ORDER BY s.vader_compound ASC
               LIMIT 10"""
        )

    data_snapshot = {
        "candidates": [
            {
                "username": c["username"],
                "display_name": c["display_name"],
                "total_posts": c["total_posts"],
                "total_comments": c["total_comments"],
                "avg_sentiment": round(float(c["avg_sentiment"]), 4),
                "sentiment": {
                    "positive": c["positive"],
                    "negative": c["negative"],
                    "neutral": c["neutral"],
                },
                "top_themes": themes_data.get(c["username"], []),
            }
            for c in candidates
        ],
        "negative_samples": [
            {
                "text": nc["text"][:200],
                "sentiment": round(float(nc["vader_compound"]), 4),
                "post_url": nc["url"],
                "candidate": nc["username"],
            }
            for nc in neg_comments
        ],
    }

    if not settings.LLM_API_KEY:
        return {
            "suggestions": [],
            "resumo_executivo": "LLM API key not configured",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_snapshot": data_snapshot,
        }

    # Build prompt
    prompt = f"""Voce e Marcelo Vitorino, um dos maiores especialistas em comunicacao politica do Brasil.
Analise os dados abaixo de campanhas no Instagram e gere sugestoes estrategicas.

DADOS:
{json.dumps(data_snapshot, ensure_ascii=False, indent=2)}

Responda APENAS com JSON valido no formato:
{{
  "resumo_executivo": "breve resumo da situacao geral",
  "suggestions": [
    {{
      "title": "titulo da sugestao",
      "description": "descricao detalhada",
      "supporting_data": "dados que sustentam a sugestao",
      "priority": "high|medium|low",
      "categoria": "engajamento|conteudo|crise|oportunidade",
      "acoes_concretas": ["acao 1", "acao 2"],
      "exemplo_post": "exemplo de post sugerido",
      "roteiro_video": "roteiro de video sugerido se aplicavel ou null",
      "publico_alvo": "publico-alvo da sugestao",
      "para_quem": "candidato(a) especifico(a)",
      "impacto_esperado": "qual impacto esperado"
    }}
  ]
}}

Gere entre 3 e 6 sugestoes priorizadas. Foque em acoes concretas e praticas."""

    try:
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
                    "temperature": 0.7,
                    "max_tokens": 3000,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Clean markdown code blocks if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            result = json.loads(content)

            # Save insights to DB
            async with pool.acquire() as conn:
                last_run = await conn.fetchrow(
                    "SELECT id FROM scraping_runs ORDER BY started_at DESC LIMIT 1"
                )
                run_id = last_run["id"] if last_run else None

                for suggestion in result.get("suggestions", []):
                    for cand in candidates:
                        if cand["username"] in suggestion.get("para_quem", ""):
                            await conn.execute(
                                """INSERT INTO strategic_insights
                                   (scraping_run_id, candidate_id, title, description,
                                    supporting_data, priority, llm_model, input_summary)
                                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)""",
                                run_id, cand["id"],
                                suggestion["title"],
                                suggestion["description"],
                                suggestion.get("supporting_data"),
                                suggestion.get("priority", "medium"),
                                settings.LLM_MODEL,
                                json.dumps(data_snapshot),
                            )
                            break

            return {
                "suggestions": result.get("suggestions", []),
                "resumo_executivo": result.get("resumo_executivo", ""),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_snapshot": data_snapshot,
            }

    except Exception as e:
        logger.error(f"Suggestions generation failed: {e}")
        return {
            "suggestions": [],
            "resumo_executivo": f"Error generating suggestions: {e}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_snapshot": data_snapshot,
        }
