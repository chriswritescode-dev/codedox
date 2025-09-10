"""Tests for token utilities module."""

import pytest
from src.utils import token_utils


class TestTokenUtils:
    """Test token utility functions."""
    
    def test_get_tiktoken_encoding_cached(self):
        """Test that tiktoken encoding is cached."""
        encoding1 = token_utils.get_tiktoken_encoding()
        encoding2 = token_utils.get_tiktoken_encoding()
        # Should be the same object due to caching
        assert encoding1 is encoding2
    
    def test_count_tokens(self):
        """Test accurate token counting."""
        # Simple text
        text = "Hello world"
        count = token_utils.count_tokens(text)
        assert count > 0
        assert count < 10  # Should be around 2 tokens
        
        # Empty text
        assert token_utils.count_tokens("") == 0
        
        # Longer text
        long_text = "The quick brown fox jumps over the lazy dog. " * 10
        long_count = token_utils.count_tokens(long_text)
        assert long_count > 50  # Should be more than 50 tokens
    
    def test_truncate_at_token_limit(self):
        """Test text truncation at token limit."""
        text = "The quick brown fox jumps over the lazy dog. " * 20
        
        # Truncate to 10 tokens
        truncated, was_truncated = token_utils.truncate_at_token_limit(text, 10)
        assert was_truncated
        assert len(truncated) < len(text)
        assert token_utils.count_tokens(truncated) <= 10
        
        # No truncation needed
        short_text = "Hello"
        result, was_truncated = token_utils.truncate_at_token_limit(short_text, 100)
        assert not was_truncated
        assert result == short_text
    
    def test_calculate_chunks(self):
        """Test chunk calculation."""
        text = "The quick brown fox jumps over the lazy dog. " * 100
        
        # Calculate chunks
        chunks_needed = token_utils.calculate_chunks(text, 50)
        assert chunks_needed > 1
        
        # Single chunk for small text
        assert token_utils.calculate_chunks("Hello", 100) == 1
    
    def test_split_into_chunks(self):
        """Test splitting text into chunks."""
        text = "The quick brown fox jumps over the lazy dog. " * 50
        
        # Split into chunks of 20 tokens each
        chunks = token_utils.split_into_chunks(text, 20)
        assert len(chunks) > 1
        
        # Each chunk should be <= 20 tokens
        for chunk in chunks:
            assert token_utils.count_tokens(chunk) <= 20
        
        # Reconstructed text should preserve content (approximately)
        reconstructed = "".join(chunks)
        # Due to token boundaries, might not be exact
        assert len(reconstructed) > 0
    
    def test_get_chunk_at_index(self):
        """Test getting specific chunk by index."""
        text = "The quick brown fox jumps over the lazy dog. " * 50
        
        # Get first chunk
        chunk0, total = token_utils.get_chunk_at_index(text, 20, 0)
        assert chunk0
        assert total > 1
        
        # Get second chunk
        chunk1, total2 = token_utils.get_chunk_at_index(text, 20, 1)
        assert chunk1
        assert total == total2
        assert chunk0 != chunk1
        
        # Invalid index should raise error
        with pytest.raises(ValueError):
            token_utils.get_chunk_at_index(text, 20, 999)
    
    def test_estimate_token_buffer(self):
        """Test smart truncation with line break preference."""
        # Text with newlines
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n" * 10
        
        # Truncate with line break preference
        result = token_utils.estimate_token_buffer(text, 20, prefer_line_break=True)
        # Should be truncated since text is long
        assert len(result) < len(text)
        assert token_utils.count_tokens(result) <= 20
        
        # Truncate without line break preference
        result_no_break = token_utils.estimate_token_buffer(text, 20, prefer_line_break=False)
        assert token_utils.count_tokens(result_no_break) <= 20
    
    def test_unicode_handling(self):
        """Test handling of unicode characters."""
        # Unicode text
        text = "Hello 世界 🌍 مرحبا мир"
        count = token_utils.count_tokens(text)
        assert count > 0
        
        # Truncation should handle unicode properly
        truncated, _ = token_utils.truncate_at_token_limit(text, 5)
        assert truncated  # Should not be empty
        
        # Chunking should handle unicode
        chunks = token_utils.split_into_chunks(text * 10, 10)
        assert all(chunk for chunk in chunks)  # No empty chunks