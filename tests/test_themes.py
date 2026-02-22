"""Unit tests for theme classification service.

Story 1.6 AC7/AC8: Keyword-based theme classification and batch processing.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chainable_table_mock() -> MagicMock:
    """Return a mock that supports fluent chaining."""
    m = MagicMock()
    for method in (
        "select", "insert", "upsert", "update", "eq", "limit",
        "in_", "gt", "lt", "is_",
    ):
        getattr(m, method).return_value = m
    return m


# ---------------------------------------------------------------------------
# AC7: classify_comment_themes
# ---------------------------------------------------------------------------


class TestClassifyCommentThemes:
    """AC7: Keyword matching for theme classification."""

    def test_single_theme_match(self) -> None:
        """AC7b/c: Text containing 'hospital' matches 'saude'."""
        from app.services.themes import classify_comment_themes

        comment_id = uuid4()
        result = classify_comment_themes(
            "Precisamos de mais hospital na regiao",
            comment_id,
        )

        assert len(result) >= 1
        themes = [t.theme.value for t in result]
        assert "saude" in themes
        assert all(t.method.value == "keyword" for t in result)
        assert all(t.confidence == 1.0 for t in result)

    def test_multiple_theme_match(self) -> None:
        """AC7b/c: Text with keywords from multiple themes matches all."""
        from app.services.themes import classify_comment_themes

        comment_id = uuid4()
        result = classify_comment_themes(
            "A policia precisa de mais escola e hospital para a populacao",
            comment_id,
        )

        themes = {t.theme.value for t in result}
        # Should match seguranca (policia), educacao (escola), saude (hospital)
        assert "seguranca" in themes
        assert "educacao" in themes
        assert "saude" in themes

    def test_no_match_returns_outros(self) -> None:
        """AC7d: No keyword match returns 'outros' with confidence 0.5."""
        from app.services.themes import classify_comment_themes

        comment_id = uuid4()
        result = classify_comment_themes(
            "Bom dia a todos",
            comment_id,
        )

        assert len(result) == 1
        assert result[0].theme.value == "outros"
        assert result[0].confidence == 0.5
        assert result[0].method.value == "keyword"

    def test_accent_normalization(self) -> None:
        """AC7a: Text with accents matches normalized keywords."""
        from app.services.themes import classify_comment_themes

        comment_id = uuid4()
        # 'educacao' and 'educacao' should both match 'educacao' keyword
        result = classify_comment_themes(
            "A educacao do Brasil precisa melhorar",
            comment_id,
        )

        themes = [t.theme.value for t in result]
        assert "educacao" in themes

    def test_case_insensitive(self) -> None:
        """AC7a: Matching is case insensitive."""
        from app.services.themes import classify_comment_themes

        comment_id = uuid4()
        result = classify_comment_themes(
            "HOSPITAL precisa de investimento",
            comment_id,
        )

        themes = [t.theme.value for t in result]
        assert "saude" in themes

    def test_comment_id_set_correctly(self) -> None:
        """ThemeCreate has the correct comment_id."""
        from app.services.themes import classify_comment_themes

        comment_id = uuid4()
        result = classify_comment_themes("hospital", comment_id)

        for theme in result:
            assert theme.comment_id == comment_id

    def test_empty_text_returns_outros(self) -> None:
        """Empty text returns outros."""
        from app.services.themes import classify_comment_themes

        result = classify_comment_themes("", uuid4())

        assert len(result) == 1
        assert result[0].theme.value == "outros"


# ---------------------------------------------------------------------------
# AC8: classify_all_unthemed_comments
# ---------------------------------------------------------------------------


class TestClassifyAllUnthemedComments:
    """AC8: Batch processing of unthemed comments."""

    @patch("app.services.themes.get_supabase")
    def test_processes_unthemed_comments(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC8a-d: Finds unthemed comments, classifies, upserts, returns count."""
        from app.services.themes import classify_all_unthemed_comments

        cid1 = str(uuid4())
        cid2 = str(uuid4())
        cid3 = str(uuid4())  # already has theme

        # Themes table already has cid3
        themes_mock = _chainable_table_mock()
        themes_mock.execute.return_value = MagicMock(
            data=[{"comment_id": cid3}]
        )

        # Comments table has all 3
        comments_mock = _chainable_table_mock()
        comments_mock.execute.return_value = MagicMock(
            data=[
                {"id": cid1, "text": "hospital precisa melhorar"},
                {"id": cid2, "text": "bom dia a todos"},
                {"id": cid3, "text": "escola precisa de mais professores"},
            ]
        )

        # Upsert mock for themes
        upsert_mock = _chainable_table_mock()
        upsert_mock.execute.return_value = MagicMock(data=[{}])

        call_count = {"n": 0}

        def table_dispatch(name: str) -> MagicMock:
            if name == "themes":
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return themes_mock  # First call is the select for existing themes
                return upsert_mock  # Subsequent calls are upserts
            if name == "comments":
                return comments_mock
            return MagicMock()

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_dispatch
        mock_get_supabase.return_value = mock_sb

        result = classify_all_unthemed_comments()

        # Should process cid1 and cid2 (cid3 already themed)
        assert result == 2

    @patch("app.services.themes.get_supabase")
    def test_no_unthemed_returns_zero(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC8: No unthemed comments returns 0."""
        from app.services.themes import classify_all_unthemed_comments

        cid1 = str(uuid4())

        themes_mock = _chainable_table_mock()
        themes_mock.execute.return_value = MagicMock(
            data=[{"comment_id": cid1}]
        )

        comments_mock = _chainable_table_mock()
        comments_mock.execute.return_value = MagicMock(
            data=[{"id": cid1, "text": "something"}]
        )

        def table_dispatch(name: str) -> MagicMock:
            if name == "themes":
                return themes_mock
            if name == "comments":
                return comments_mock
            return MagicMock()

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_dispatch
        mock_get_supabase.return_value = mock_sb

        result = classify_all_unthemed_comments()

        assert result == 0
