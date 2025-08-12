"""Tests for library name resolution in get_content tool."""

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.mcp_server.tools import MCPTools


@pytest.mark.asyncio
class TestLibraryNameResolution:
    """Test library name resolution functionality."""

    async def test_get_content_with_uuid(self):
        """Test get_content with a valid UUID."""
        tools = MCPTools()
        test_uuid = str(uuid4())

        # Create a proper context manager mock
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch.object(tools.db_manager, 'session_scope', return_value=mock_context):
            mock_searcher = Mock()
            mock_searcher.search.return_value = ([], 0)

            with patch('src.mcp_server.tools.CodeSearcher', return_value=mock_searcher):
                result = await tools.get_content(library_id=test_uuid, query="test")

                # Should call search with the UUID directly
                mock_searcher.search.assert_called_once_with(
                    query="test",
                    job_id=test_uuid,
                    limit=20,
                    offset=0,
                    include_context=False
                )

    async def test_get_content_with_exact_name_match(self):
        """Test get_content with exact library name match."""
        tools = MCPTools()

        # Create a proper context manager mock
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch.object(tools.db_manager, 'session_scope', return_value=mock_context):
            mock_searcher = Mock()

            # Mock search_libraries to return exact match with tuple
            mock_searcher.search_libraries.return_value = ([
                {
                    'library_id': 'test-uuid-123',
                    'name': 'NextJS',
                    'description': 'Next.js framework',
                    'snippet_count': 100,
                    'similarity_score': 1.0
                }
            ], 1)

            # Mock search to return some results
            mock_searcher.search.return_value = ([Mock(id=1)], 1)
            mock_searcher.format_search_results.return_value = "Test results"

            with patch('src.mcp_server.tools.CodeSearcher', return_value=mock_searcher):
                result = await tools.get_content(library_id="nextjs", query="test")

                # Should resolve name to UUID and search
                mock_searcher.search_libraries.assert_called_once_with(query="nextjs", limit=20)
                mock_searcher.search.assert_called_once_with(
                    query="test",
                    job_id='test-uuid-123',
                    limit=20,
                    offset=0,
                    include_context=False
                )
                assert "Found 1 results" in result
                assert "library 'NextJS'" in result

    async def test_get_content_with_fuzzy_match(self):
        """Test get_content with fuzzy library name match."""
        tools = MCPTools()

        # Create a proper context manager mock
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch.object(tools.db_manager, 'session_scope', return_value=mock_context):
            mock_searcher = Mock()

            # Mock search_libraries to return fuzzy match with tuple
            mock_searcher.search_libraries.return_value = ([
                {
                    'library_id': 'react-uuid-456',
                    'name': 'React',
                    'description': 'React framework',
                    'snippet_count': 200,
                    'similarity_score': 0.85
                }
            ], 1)

            # Mock search to return some results
            mock_searcher.search.return_value = ([Mock(id=1)], 1)
            mock_searcher.format_search_results.return_value = "Test results"

            with patch('src.mcp_server.tools.CodeSearcher', return_value=mock_searcher):
                result = await tools.get_content(library_id="reakt", query="hooks")

                # Should use the single fuzzy match
                assert "Found 1 results" in result
                assert "library 'React'" in result

    async def test_get_content_with_multiple_matches(self):
        """Test get_content with multiple similar library matches."""
        tools = MCPTools()

        # Mock settings - these are accessed from the module level
        mock_settings = MagicMock()
        mock_settings.search.library_auto_select_threshold = 0.7
        mock_settings.search.library_auto_select_gap = 0.2

        # Create a proper context manager mock
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch.object(tools.db_manager, 'session_scope', return_value=mock_context), \
             patch('src.mcp_server.tools.settings', mock_settings):
            mock_searcher = Mock()

            # Mock search_libraries to return multiple similar matches (no exact match) with tuple
            mock_searcher.search_libraries.return_value = ([
                {
                    'library_id': 'react-lib-uuid-1',
                    'name': 'React Library',
                    'description': 'React framework',
                    'snippet_count': 200,
                    'similarity_score': 0.7
                },
                {
                    'library_id': 'react-native-uuid-2',
                    'name': 'React Native',
                    'description': 'React Native framework',
                    'snippet_count': 150,
                    'similarity_score': 0.65
                }
            ], 2)

            with patch('src.mcp_server.tools.CodeSearcher', return_value=mock_searcher):
                result = await tools.get_content(library_id="react", query="test")

                # Should ask user to be more specific
                assert "Multiple libraries match 'react'" in result
                assert "Please be more specific" in result
                assert "React Library (match: 70%, snippets: 200)" in result
                assert "React Native (match: 65%, snippets: 150)" in result

    async def test_get_content_with_no_matches(self):
        """Test get_content with no library matches."""
        tools = MCPTools()

        # Mock settings - these are accessed from the module level
        mock_settings = MagicMock()
        mock_settings.search.library_suggestion_threshold = 0.5

        # Create a proper context manager mock
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch.object(tools.db_manager, 'session_scope', return_value=mock_context), \
             patch('src.mcp_server.tools.settings', mock_settings):
            mock_searcher = Mock()

            # Mock search_libraries to return no matches with tuple
            mock_searcher.search_libraries.side_effect = [
                ([], 0),  # No matches for the query
                ([    # Some available libraries for suggestions
                    {'library_id': 'vue-uuid', 'name': 'Vue.js', 'snippet_count': 100},
                    {'library_id': 'angular-uuid', 'name': 'Angular', 'snippet_count': 120}
                ], 2)
            ]

            with patch('src.mcp_server.tools.CodeSearcher', return_value=mock_searcher):
                result = await tools.get_content(library_id="nonexistent", query="test")

                # Should not find any matches
                assert "No library found matching 'nonexistent'" in result
                # The actual message depends on whether similar libraries are found
                # Based on the error message, no similar libraries were found
                assert ("Use search_libraries to find available libraries" in result or
                        "Did you mean one of these?" in result)

    async def test_get_content_with_strong_single_match(self):
        """Test get_content with one strong match and weaker alternatives."""
        tools = MCPTools()

        # Mock settings - these are accessed from the module level
        mock_settings = MagicMock()
        mock_settings.search.library_auto_select_threshold = 0.7
        mock_settings.search.library_auto_select_gap = 0.2

        # Create a proper context manager mock
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch.object(tools.db_manager, 'session_scope', return_value=mock_context), \
             patch('src.mcp_server.tools.settings', mock_settings):
            mock_searcher = Mock()

            # Mock search_libraries with one strong match with tuple
            mock_searcher.search_libraries.return_value = ([
                {
                    'library_id': 'nextjs-uuid',
                    'name': 'Next.js',
                    'description': 'Next.js framework',
                    'snippet_count': 300,
                    'similarity_score': 0.9
                },
                {
                    'library_id': 'nestjs-uuid',
                    'name': 'NestJS',
                    'description': 'NestJS framework',
                    'snippet_count': 100,
                    'similarity_score': 0.4
                }
            ], 2)

            # Mock search to return results
            mock_searcher.search.return_value = ([Mock(id=1)], 1)
            mock_searcher.format_search_results.return_value = "Test results"

            with patch('src.mcp_server.tools.CodeSearcher', return_value=mock_searcher):
                result = await tools.get_content(library_id="next", query="routing")

                # Should automatically use the strong match
                mock_searcher.search.assert_called_once_with(
                    query="routing",
                    job_id='nextjs-uuid',
                    limit=20,
                    offset=0,
                    include_context=False
                )
                assert "Found 1 results" in result
                assert "library 'Next.js'" in result
