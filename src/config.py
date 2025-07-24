"""Configuration management for CodeDox."""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional, List, Any
from pydantic import Field
from pydantic.types import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv()

logger = logging.getLogger(__name__)  


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

    host: str = "localhost"
    port: int = 5432
    name: str = "codedox"
    user: str = "postgres"
    password: str = "postgres"

    @property
    def url(self) -> str:
        """Build PostgreSQL connection URL."""
        from urllib.parse import quote_plus

        # URL encode the password to handle special characters
        encoded_password = quote_plus(self.password)
        return f"postgresql+psycopg://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.name}"



class MCPConfig(BaseSettings):
    """MCP server configuration.

    Note: These settings are only used for the standalone stdio-based MCP server.
    When using HTTP mode (recommended), MCP tools are served via the main API server
    on the API_PORT (default 8000).
    """
    model_config = SettingsConfigDict(env_prefix="MCP_", extra="allow")

    port: int = 8899  # Only used for standalone stdio server
    host: str = "localhost"  # Only used for standalone stdio server
    max_connections: int = 10
    tools: List[str] = ["init_crawl", "get_sources", "get_content"]


class CrawlingConfig(BaseSettings):
    """Web crawling configuration."""
    model_config = SettingsConfigDict(env_prefix="CRAWL_", extra="allow")

    default_max_depth: int = 2
    max_pages_per_job: int = 500
    respect_robots_txt: bool = True
    max_concurrent_pages: int = 3
    content_size_limit: int = 50000
    user_agent: str = "CodeDox/1.0 (Documentation Crawler)"
    max_concurrent_sessions: int = 20


class CodeExtractionConfig(BaseSettings):
    """Code extraction configuration."""
    model_config = SettingsConfigDict(env_prefix="CODE_", extra="allow")

    max_code_block_size: int = 50000
    preserve_context_chars: int = 500
    min_code_lines: int = 2
    
    # LLM extraction configuration
    llm_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="API key for LLM extraction (OpenAI-compatible)"
    )
    llm_extraction_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for code extraction"
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for LLM API (if using custom endpoint)"
    )
    enable_context_extraction: bool = Field(
        default=True,
        description="Extract surrounding context for code blocks"
    )
    max_context_length: int = Field(
        default=1000,
        description="Maximum characters of context to extract around code blocks"
    )


class SearchConfig(BaseSettings):
    """Search configuration."""
    model_config = SettingsConfigDict(env_prefix="SEARCH_", extra="allow")

    max_results: int = 50
    enable_fuzzy_search: bool = True
    boost_recent_days: int = 7
    snippet_preview_length: int = 200
    default_max_results: int = 10
    min_score: float = 0.1
    
    # Library name matching thresholds
    library_exact_match_threshold: float = 1.0  # Exact match always wins
    library_auto_select_threshold: float = 0.7  # Minimum score to auto-select
    library_auto_select_gap: float = 0.2  # Minimum gap between 1st and 2nd match
    library_suggestion_threshold: float = 0.3  # Minimum score to show as suggestion
    
    # Relationship-based search
    include_related_snippets: bool = True  # Include related snippets in search results


class APIConfig(BaseSettings):
    """API server configuration."""
    model_config = SettingsConfigDict(env_prefix="API_", extra="allow")
    
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]
    max_request_size: int = 10485760  # 10MB


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    model_config = SettingsConfigDict(env_prefix="LOG_", extra="allow")

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = "logs/codedox.log"
    max_size: int = 10485760  # 10MB
    backup_count: int = 5


class Settings(BaseSettings):
    """Main application settings."""

    # General settings
    output_separator: str = "----------------------------------------"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
        validate_assignment=True,
    )
    
    def __init__(self, **kwargs: Any) -> None:
        """Initialize settings with sub-configurations."""
        super().__init__(**kwargs)
        
        # Initialize sub-configurations
        self.database = DatabaseConfig()
        self.mcp = MCPConfig()
        self.crawling = CrawlingConfig()
        self.code_extraction = CodeExtractionConfig()
        self.search = SearchConfig()
        self.api = APIConfig()
        self.logging = LoggingConfig()

    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        log_level = getattr(logging, self.logging.level.upper(), logging.INFO)

        # Create logs directory if needed
        if self.logging.file:
            log_dir = Path(self.logging.file).parent
            log_dir.mkdir(parents=True, exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=log_level,
            format=self.logging.format,
            handlers=[
                logging.StreamHandler(),
                logging.handlers.RotatingFileHandler(
                    self.logging.file,
                    maxBytes=self.logging.max_size,
                    backupCount=self.logging.backup_count
                ) if self.logging.file else logging.NullHandler()
            ]
        )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.setup_logging()
    return _settings


# Convenience exports
settings = get_settings()
