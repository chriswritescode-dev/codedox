"""Tests for limit=0 handling across search methods."""

import pytest
from unittest.mock import MagicMock, patch
from src.database.search import CodeSearcher
from src.database.models import CodeSnippet


class TestLimitHandling:
    """Test that limit=0 is handled correctly across all search methods."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def searcher(self, mock_session):
        """Create a CodeSearcher instance with mock session."""
        return CodeSearcher(mock_session)
    
    def test_search_with_limit_zero(self, searcher, mock_session):
        """Test main search method with limit=0."""
        # Mock the query to return empty results when limit is 0
        mock_query = MagicMock()
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        mock_session.execute.return_value.fetchall.return_value = []
        mock_session.execute.return_value.scalar.return_value = 0
        
        # Test with limit=0
        results, total = searcher.search(query="test", limit=0)
        assert results == []
        assert total == 0
    
    def test_search_with_limit_none(self, searcher):
        """Test search with limit=None uses default."""
        with patch.object(searcher, 'settings') as mock_settings:
            mock_settings.default_max_results = 10
            mock_settings.markdown_fallback_threshold = 5
            mock_settings.markdown_fallback_enabled = False  # Disable to simplify test
            
            # Create a mock that tracks the limit value
            actual_limit = None
            
            # Mock both execute calls (main query and count query)
            def execute_with_limit(text_obj, params=None):
                nonlocal actual_limit
                if params and 'limit' in params:
                    actual_limit = params.get('limit')
                result = MagicMock()
                result.fetchall.return_value = []
                result.scalar.return_value = 0
                return result
            
            searcher.session.execute = execute_with_limit
            
            # Search with limit=None should use default
            searcher.search(query="test", limit=None)
            assert actual_limit == 10
    
    def test_search_by_function_with_limit_zero(self, searcher, mock_session):
        """Test search_by_function with limit=0."""
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        
        results = searcher.search_by_function("test_func", limit=0)
        assert results == []
        
        # Verify limit(0) was called
        mock_query.limit.assert_called_with(0)
    
    def test_search_by_import_with_limit_zero(self, searcher, mock_session):
        """Test search_by_import with limit=0."""
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        
        results = searcher.search_by_import("numpy", limit=0)
        assert results == []
        
        # Verify limit(0) was called
        mock_query.limit.assert_called_with(0)
    
    def test_search_similar_with_limit_zero(self, searcher, mock_session):
        """Test search_similar with limit=0."""
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        
        results = searcher.search_similar("similar text", limit=0)
        assert results == []
        
        # Verify limit(0) was called
        mock_query.limit.assert_called_with(0)
    
    def test_get_recent_snippets_with_limit_zero(self, searcher, mock_session):
        """Test get_recent_snippets with limit=0."""
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        
        results = searcher.get_recent_snippets(limit=0)
        assert results == []
        
        # Verify limit(0) was called
        mock_query.limit.assert_called_with(0)
    
    def test_positive_limits_work(self, searcher, mock_session):
        """Test that positive limits still work correctly."""
        # Create mock snippets
        mock_snippets = [MagicMock(spec=CodeSnippet) for _ in range(5)]
        
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_snippets[:3]  # Return 3 items
        mock_session.query.return_value = mock_query
        
        results = searcher.search_by_function("test", limit=3)
        assert len(results) == 3
        
        # Verify limit(3) was called
        mock_query.limit.assert_called_with(3)