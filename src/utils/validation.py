"""Input validation utilities for secure parameter handling."""

import re
from typing import Any


def validate_snippet_id(snippet_id: str | int | None) -> int:
    """Validate and convert snippet ID to integer.
    
    Args:
        snippet_id: The snippet ID to validate (can be string, int, or None)
        
    Returns:
        Valid integer snippet ID
        
    Raises:
        ValueError: If snippet_id is invalid
        TypeError: If snippet_id is wrong type
    """
    if snippet_id is None:
        raise ValueError("Snippet ID cannot be None")
    
    if isinstance(snippet_id, int):
        if snippet_id < 0:
            raise ValueError(f"Invalid snippet ID: {snippet_id} (must be positive)")
        return snippet_id
    
    if isinstance(snippet_id, str):
        # Strip whitespace
        snippet_id = snippet_id.strip()
        
        # Check if it's a valid number
        if not snippet_id.isdigit():
            raise ValueError(f"Invalid snippet ID format: '{snippet_id}' (must be numeric)")
        
        result = int(snippet_id)
        if result < 0:
            raise ValueError(f"Invalid snippet ID: {result} (must be positive)")
        
        return result
    
    raise TypeError(f"Snippet ID must be string or int, not {type(snippet_id).__name__}")


def validate_uuid(value: str) -> bool:
    """Validate if a string is a valid UUID.
    
    Args:
        value: String to validate
        
    Returns:
        True if valid UUID, False otherwise
    """
    if not isinstance(value, str):
        return False
    
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", 
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


def validate_positive_integer(value: Any, name: str, max_value: int | None = None) -> int:
    """Validate and convert a value to a positive integer.
    
    Args:
        value: Value to validate
        name: Name of the parameter (for error messages)
        max_value: Optional maximum allowed value
        
    Returns:
        Valid positive integer
        
    Raises:
        ValueError: If value is invalid
        TypeError: If value is wrong type
    """
    if value is None:
        raise ValueError(f"{name} cannot be None")
    
    if isinstance(value, bool):
        # Explicitly reject booleans (True/False are technically int subclasses)
        raise TypeError(f"{name} must be an integer, not boolean")
    
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"{name} must be an integer, not a float with decimal places")
        
        int_value = int(value)
    elif isinstance(value, str):
        try:
            int_value = int(value.strip())
        except ValueError:
            raise ValueError(f"{name} must be a valid integer, got '{value}'")
    else:
        raise TypeError(f"{name} must be an integer or string, not {type(value).__name__}")
    
    if int_value < 0:
        raise ValueError(f"{name} must be positive, got {int_value}")
    
    if max_value is not None and int_value > max_value:
        raise ValueError(f"{name} must not exceed {max_value}, got {int_value}")
    
    return int_value


def validate_chunk_index(chunk_index: Any, total_chunks: int | None = None) -> int:
    """Validate chunk index parameter.
    
    Args:
        chunk_index: The chunk index to validate
        total_chunks: Optional total number of chunks to validate against
        
    Returns:
        Valid chunk index
        
    Raises:
        ValueError: If chunk_index is invalid
    """
    if chunk_index is None:
        raise ValueError("Chunk index cannot be None")
    
    index = validate_positive_integer(chunk_index, "Chunk index", max_value=10000)
    
    if total_chunks is not None and index >= total_chunks:
        raise ValueError(
            f"Chunk index {index} out of range (total chunks: {total_chunks})"
        )
    
    return index