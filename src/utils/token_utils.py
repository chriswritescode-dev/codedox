"""Token utilities using tiktoken for accurate token counting."""

import tiktoken
from functools import lru_cache
from typing import Tuple


@lru_cache(maxsize=1)
def get_tiktoken_encoding():
    """Get cached tiktoken encoding for cl100k_base model."""
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count exact tokens in text using tiktoken.
    
    Args:
        text: The text to count tokens for
        
    Returns:
        Number of tokens in the text
    """
    encoding = get_tiktoken_encoding()
    return len(encoding.encode(text))


def truncate_at_token_limit(text: str, max_tokens: int) -> Tuple[str, bool]:
    """Truncate text to max_tokens, returning (truncated_text, was_truncated).
    
    Args:
        text: The text to potentially truncate
        max_tokens: Maximum number of tokens allowed
        
    Returns:
        Tuple of (truncated_text, was_truncated)
    """
    encoding = get_tiktoken_encoding()
    tokens = encoding.encode(text)
    
    if len(tokens) <= max_tokens:
        return text, False
    
    # Truncate and decode
    truncated_tokens = tokens[:max_tokens]
    truncated_text = encoding.decode(truncated_tokens)
    return truncated_text, True


def calculate_chunks(text: str, tokens_per_chunk: int) -> int:
    """Calculate number of chunks needed based on actual token count.
    
    Args:
        text: The text to chunk
        tokens_per_chunk: Number of tokens per chunk
        
    Returns:
        Number of chunks needed
    """
    total_tokens = count_tokens(text)
    return (total_tokens + tokens_per_chunk - 1) // tokens_per_chunk


def split_into_chunks(text: str, tokens_per_chunk: int) -> list[str]:
    """Split text into chunks of approximately tokens_per_chunk tokens.
    
    Args:
        text: The text to split
        tokens_per_chunk: Target number of tokens per chunk
        
    Returns:
        List of text chunks
    """
    encoding = get_tiktoken_encoding()
    tokens = encoding.encode(text)
    
    chunks = []
    for i in range(0, len(tokens), tokens_per_chunk):
        chunk_tokens = tokens[i:i + tokens_per_chunk]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
    
    return chunks


def get_chunk_at_index(text: str, tokens_per_chunk: int, chunk_index: int) -> Tuple[str, int]:
    """Get a specific chunk by index.
    
    Args:
        text: The text to chunk
        tokens_per_chunk: Number of tokens per chunk
        chunk_index: 0-based index of the chunk to retrieve
        
    Returns:
        Tuple of (chunk_text, total_chunks)
    """
    chunks = split_into_chunks(text, tokens_per_chunk)
    total_chunks = len(chunks)
    
    if chunk_index >= total_chunks:
        raise ValueError(f"Chunk index {chunk_index} out of range (total chunks: {total_chunks})")
    
    return chunks[chunk_index], total_chunks


def estimate_token_buffer(text: str, target_tokens: int, prefer_line_break: bool = True) -> str:
    """Get text that fits within target_tokens with smart truncation.
    
    Args:
        text: The text to truncate
        target_tokens: Target number of tokens
        prefer_line_break: Whether to prefer truncating at line boundaries
        
    Returns:
        Truncated text that fits within token limit
    """
    encoding = get_tiktoken_encoding()
    tokens = encoding.encode(text)
    
    if len(tokens) <= target_tokens:
        return text
    
    # Truncate to target tokens
    truncated_tokens = tokens[:target_tokens]
    truncated_text = encoding.decode(truncated_tokens)
    
    if not prefer_line_break:
        return truncated_text
    
    # Try to truncate at a line boundary for cleaner output
    # Look for last newline in the last 20% of text
    last_portion = int(len(truncated_text) * 0.8)
    last_newline = truncated_text.rfind('\n', last_portion)
    
    if last_newline > 0:
        return truncated_text[:last_newline]
    
    return truncated_text