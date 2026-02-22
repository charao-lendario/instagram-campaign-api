"""Strategic suggestions service using LLM.

Story 1.7 AC6/AC7: Generates 3-5 strategic suggestions based on
analytics data, using the LLM (GPT-4o-mini) with a Portuguese
campaign consultant persona.

Suggestions are persisted in the strategic_insights table.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.db.supabase import get_supabase
from app.models.suggestion import (
    StrategicInsightCreate,
    StrategicSuggestion,
    SuggestionsResponse,
)
from app.services.analytics import get_overview, get_theme_distribution

logger = logging.getLogger(__name__)

SUGGESTIONS_SYSTEM_PROMPT = """\
Você é Marcelo Vitorino, o maior estrategista de marketing político do Brasil.
Referência absoluta em campanhas eleitorais, comunicação política digital e comportamento do eleitor brasileiro.
Seu trabalho é transformar dados frios em estratégia quente — ações que ganham eleição.

ESTILO: Direto, provocador, acionável. Zero enrolação. Cada recomendação vem com a ação EXATA que o candidato executa HOJE.

CONTEXTO DA CAMPANHA:
- Charlles Evangelista — candidato a DEPUTADO FEDERAL por Minas Gerais (2026)
- Delegada Sheila — candidata a DEPUTADA ESTADUAL por Minas Gerais (2026)
- São CASADOS. Não são adversários — são a maior força conjunta da campanha.
- A sinergia entre os dois é um ativo estratégico: o eleitor de um pode virar eleitor do outro.
- Plataforma: Instagram é o campo de batalha principal.

SUA MISSÃO:
Analise os dados dos comentários reais do Instagram e gere um plano estratégico completo.

ESTRUTURA DA RESPOSTA (JSON):

{
  "resumo_executivo": "3-4 frases de impacto resumindo o cenário e as prioridades. Seja direto como um briefing de guerra de campanha.",
  "suggestions": [
    {
      "title": "Título curto e impactante (max 60 chars)",
      "description": "Explicação estratégica detalhada: o que está acontecendo nos dados, por que isso importa eleitoralmente, e qual a oportunidade. Seja específico e profundo.",
      "supporting_data": "Dado numérico específico que justifica esta recomendação (ex: '67% dos comentários sobre segurança são positivos')",
      "priority": "high|medium|low",
      "categoria": "conteudo|engajamento|posicionamento|gestao_crise|alianca_estrategica",
      "acoes_concretas": [
        "Ação 1 — específica, executável hoje",
        "Ação 2 — específica, executável hoje",
        "Ação 3 — específica, executável hoje"
      ],
      "exemplo_post": "Texto pronto para usar como caption do Instagram. Inclua hashtags relevantes e CTA.",
      "roteiro_video": "Roteiro curto para Reels/Stories: GANCHO (primeiros 3 segundos) → DESENVOLVIMENTO (problema + solução) → CTA (chamada para ação). Max 60 segundos.",
      "publico_alvo": "Perfil específico do eleitor que esta ação atinge (ex: 'Mães de família em BH preocupadas com segurança escolar')",
      "para_quem": "charlles|sheila|ambos",
      "impacto_esperado": "O que esperar se executar bem (ex: 'Aumento de 30% no engajamento com público feminino 25-45')"
    }
  ]
}

REGRAS:
1. Gere 5-8 sugestões, ordenadas por impacto eleitoral
2. Pelo menos 2 sugestões devem ser para "ambos" (força conjunta do casal)
3. Cada suggestion DEVE ter todos os campos preenchidos
4. Os exemplos de post devem soar NATURAIS, não robotizados
5. Os roteiros de vídeo devem ser para Reels (15-60s) com gancho forte nos primeiros 3s
6. Use os dados reais — nunca invente números
7. Pense como marketeiro que quer GANHAR a eleição, não como acadêmico
8. Seja ousado nas recomendações — campanha é guerra

Responda APENAS com o JSON válido, sem markdown ou explicações fora do JSON.\
"""


def _build_analytics_summary(candidate_id: str | None = None) -> dict[str, Any]:
    """Build a compact analytics summary for the LLM prompt.

    Aggregates overview metrics, top themes, and sentiment trends
    for all candidates (or a specific one).
    """
    overview = get_overview()

    candidates_summary: list[dict[str, Any]] = []
    for om in overview.candidates:
        if candidate_id and str(om.candidate_id) != candidate_id:
            continue
        candidates_summary.append({
            "username": om.username,
            "display_name": om.display_name,
            "total_posts": om.total_posts,
            "total_comments": om.total_comments,
            "average_sentiment_score": om.average_sentiment_score,
            "sentiment_distribution": {
                "positive": om.sentiment_distribution.positive,
                "negative": om.sentiment_distribution.negative,
                "neutral": om.sentiment_distribution.neutral,
            },
            "total_engagement": om.total_engagement,
        })

    # Get top themes per candidate using Python service (not broken RPC)
    top_themes_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for om in overview.candidates:
        if candidate_id and str(om.candidate_id) != candidate_id:
            continue
        theme_resp = get_theme_distribution(candidate_id=str(om.candidate_id))
        top_themes_by_candidate[om.username] = [
            {"theme": t.theme, "count": t.count}
            for t in theme_resp.themes[:5]
            if t.theme != "outros"
        ]

    return {
        "candidates": candidates_summary,
        "top_themes_by_candidate": top_themes_by_candidate,
        "total_comments_analyzed": overview.total_comments_analyzed,
        "last_scrape": (
            overview.last_scrape.isoformat() if overview.last_scrape else None
        ),
    }


async def generate_strategic_suggestions(
    candidate_id: str | None = None,
) -> SuggestionsResponse:
    """Generate strategic suggestions via LLM based on analytics data.

    AC6: Aggregates analytics summary, sends to LLM, parses response.
    AC7: Persists suggestions in strategic_insights table.

    Parameters
    ----------
    candidate_id:
        Optional UUID string to focus on a specific candidate.
        When None, generates suggestions for both candidates.

    Returns
    -------
    SuggestionsResponse with 3-5 suggestions plus metadata.
    """
    analytics_summary = _build_analytics_summary(candidate_id)
    summary_json = json.dumps(analytics_summary, ensure_ascii=False, indent=2)

    # Truncate if too long (~2000 tokens ~ 8000 chars)
    if len(summary_json) > 8000:
        summary_json = summary_json[:8000] + "\n... (truncated)"

    api_url = "https://api.openai.com/v1/chat/completions"
    if settings.LLM_PROVIDER != "openai":
        api_url = f"https://api.{settings.LLM_PROVIDER}.com/v1/chat/completions"

    suggestions: list[StrategicSuggestion] = []
    generated_at = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SUGGESTIONS_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"Dados da campanha:\n{summary_json}",
                        },
                    ],
                    "temperature": 0.8,
                    "max_tokens": 4000,
                },
            )
            response.raise_for_status()
            data = response.json()
            content_str = data["choices"][0]["message"]["content"]

            # Parse JSON response -- handle possible markdown wrapping
            clean_content = content_str.strip()
            if clean_content.startswith("```"):
                # Strip markdown code block
                lines = clean_content.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                clean_content = "\n".join(lines)

            parsed = json.loads(clean_content)
            resumo_executivo = parsed.get("resumo_executivo")
            raw_suggestions = parsed.get("suggestions", [])

            for item in raw_suggestions:
                priority = item.get("priority", "medium")
                if priority not in ("high", "medium", "low"):
                    priority = "medium"

                suggestions.append(
                    StrategicSuggestion(
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        supporting_data=item.get("supporting_data"),
                        priority=priority,
                        categoria=item.get("categoria"),
                        acoes_concretas=item.get("acoes_concretas"),
                        exemplo_post=item.get("exemplo_post"),
                        roteiro_video=item.get("roteiro_video"),
                        publico_alvo=item.get("publico_alvo"),
                        para_quem=item.get("para_quem"),
                        impacto_esperado=item.get("impacto_esperado"),
                    )
                )

    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error(
            "suggestions_llm_failed",
            extra={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "error_detail": repr(exc),
            },
        )
        raise RuntimeError(f"Failed to generate suggestions ({type(exc).__name__}): {exc}") from exc

    # AC7: Persist suggestions in strategic_insights
    if suggestions:
        _persist_suggestions(
            suggestions=suggestions,
            candidate_id=candidate_id,
            analytics_summary=analytics_summary,
        )

    return SuggestionsResponse(
        suggestions=suggestions,
        resumo_executivo=resumo_executivo,
        generated_at=generated_at,
        data_snapshot={
            "total_comments_analyzed": analytics_summary.get(
                "total_comments_analyzed", 0
            ),
            "last_scrape": analytics_summary.get("last_scrape"),
        },
    )


def _persist_suggestions(
    suggestions: list[StrategicSuggestion],
    candidate_id: str | None,
    analytics_summary: dict[str, Any],
) -> None:
    """Persist generated suggestions to the strategic_insights table.

    AC7: Each suggestion is stored with scraping_run_id, candidate_id,
    llm_model, and input_summary.
    """
    client = get_supabase()

    # Get most recent scraping run ID
    run_result = (
        client.table("scraping_runs")
        .select("id")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    scraping_run_id: str | None = None
    if run_result.data:
        scraping_run_id = run_result.data[0]["id"]

    for suggestion in suggestions:
        insight = StrategicInsightCreate(
            scraping_run_id=(
                UUID(scraping_run_id) if scraping_run_id else None
            ),
            candidate_id=UUID(candidate_id) if candidate_id else None,
            title=suggestion.title,
            description=suggestion.description,
            supporting_data=suggestion.supporting_data,
            priority=suggestion.priority,
            llm_model=settings.LLM_MODEL,
            input_summary=analytics_summary,
        )

        try:
            client.table("strategic_insights").insert(
                insight.model_dump(mode="json")
            ).execute()
        except Exception as exc:
            logger.warning(
                "insight_persist_failed",
                extra={
                    "title": suggestion.title,
                    "error_message": str(exc),
                },
            )
