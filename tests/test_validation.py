"""Tests for validation utilities."""

import pytest
from src.utils import validation


class TestValidation:
    """Test validation utility functions."""
    
    def test_validate_snippet_id_with_int(self):
        """Test snippet ID validation with integers."""
        # Valid positive integer
        assert validation.validate_snippet_id(123) == 123
        assert validation.validate_snippet_id(0) == 0
        
        # Negative integer should fail
        with pytest.raises(ValueError, match="must be positive"):
            validation.validate_snippet_id(-1)
    
    def test_validate_snippet_id_with_string(self):
        """Test snippet ID validation with strings."""
        # Valid string numbers
        assert validation.validate_snippet_id("123") == 123
        assert validation.validate_snippet_id("  456  ") == 456  # With whitespace
        assert validation.validate_snippet_id("0") == 0
        
        # Invalid string formats
        with pytest.raises(ValueError, match="must be numeric"):
            validation.validate_snippet_id("abc")
        
        with pytest.raises(ValueError, match="must be numeric"):
            validation.validate_snippet_id("12.34")
        
        with pytest.raises(ValueError, match="must be numeric"):
            validation.validate_snippet_id("")
    
    def test_validate_snippet_id_with_none(self):
        """Test snippet ID validation with None."""
        with pytest.raises(ValueError, match="cannot be None"):
            validation.validate_snippet_id(None)
    
    def test_validate_snippet_id_with_wrong_type(self):
        """Test snippet ID validation with wrong types."""
        with pytest.raises(TypeError):
            validation.validate_snippet_id([123])
        
        with pytest.raises(TypeError):
            validation.validate_snippet_id({"id": 123})
    
    def test_validate_snippet_id_large_values(self):
        """Test snippet ID validation with large values."""
        # Large values should be valid (PostgreSQL can handle them)
        assert validation.validate_snippet_id(2147483647) == 2147483647
        assert validation.validate_snippet_id("9999999999999") == 9999999999999
    
    def test_validate_uuid(self):
        """Test UUID validation."""
        # Valid UUIDs
        assert validation.validate_uuid("12345678-1234-1234-1234-123456789012")
        assert validation.validate_uuid("a0b1c2d3-e4f5-6789-abcd-ef0123456789")
        assert validation.validate_uuid("A0B1C2D3-E4F5-6789-ABCD-EF0123456789")  # Uppercase
        
        # Invalid UUIDs
        assert not validation.validate_uuid("not-a-uuid")
        assert not validation.validate_uuid("12345678-1234-1234-1234")  # Too short
        assert not validation.validate_uuid("12345678-1234-1234-1234-12345678901g")  # Invalid char
        assert not validation.validate_uuid("")
        assert not validation.validate_uuid(None)
        assert not validation.validate_uuid(123)
    
    def test_validate_positive_integer(self):
        """Test positive integer validation."""
        # Valid values
        assert validation.validate_positive_integer(10, "test") == 10
        assert validation.validate_positive_integer(0, "test") == 0
        assert validation.validate_positive_integer("42", "test") == 42
        assert validation.validate_positive_integer(3.0, "test") == 3  # Float with no decimals
        
        # Invalid values
        with pytest.raises(ValueError, match="must be positive"):
            validation.validate_positive_integer(-5, "test")
        
        with pytest.raises(ValueError, match="cannot be None"):
            validation.validate_positive_integer(None, "test")
        
        with pytest.raises(ValueError, match="not a float with decimal"):
            validation.validate_positive_integer(3.14, "test")
        
        with pytest.raises(TypeError, match="not boolean"):
            validation.validate_positive_integer(True, "test")
    
    def test_validate_positive_integer_with_max(self):
        """Test positive integer validation with maximum value."""
        # Within max
        assert validation.validate_positive_integer(50, "test", max_value=100) == 50
        assert validation.validate_positive_integer(100, "test", max_value=100) == 100
        
        # Exceeding max
        with pytest.raises(ValueError, match="must not exceed 100"):
            validation.validate_positive_integer(101, "test", max_value=100)
    
    def test_validate_chunk_index(self):
        """Test chunk index validation."""
        # Valid indices
        assert validation.validate_chunk_index(0) == 0
        assert validation.validate_chunk_index(5) == 5
        assert validation.validate_chunk_index("10") == 10
        
        # Invalid indices
        with pytest.raises(ValueError, match="cannot be None"):
            validation.validate_chunk_index(None)
        
        with pytest.raises(ValueError, match="must be positive"):
            validation.validate_chunk_index(-1)
        
        # With total chunks validation
        assert validation.validate_chunk_index(2, total_chunks=5) == 2
        
        with pytest.raises(ValueError, match="out of range"):
            validation.validate_chunk_index(5, total_chunks=5)  # 0-indexed, so 5 is out of range
        
        with pytest.raises(ValueError, match="out of range"):
            validation.validate_chunk_index(10, total_chunks=3)