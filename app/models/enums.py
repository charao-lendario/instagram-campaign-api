"""Enum types mirroring PostgreSQL custom enums from SCHEMA.md."""

from enum import Enum


class SentimentLabel(str, Enum):
    """Sentiment classification output."""
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class ScrapingStatus(str, Enum):
    """Lifecycle status of a scraping run."""
    running = "running"
    success = "success"
    failed = "failed"
    partial = "partial"


class ThemeCategory(str, Enum):
    """Predefined thematic categories (PT-BR political context)."""
    saude = "saude"
    seguranca = "seguranca"
    educacao = "educacao"
    economia = "economia"
    infraestrutura = "infraestrutura"
    corrupcao = "corrupcao"
    emprego = "emprego"
    meio_ambiente = "meio_ambiente"
    outros = "outros"


class AnalysisMethod(str, Enum):
    """Method used for classification."""
    keyword = "keyword"
    llm = "llm"


class MediaType(str, Enum):
    """Instagram post media type."""
    image = "image"
    video = "video"
    carousel = "carousel"
    unknown = "unknown"
