"""Configuration management for the RAG pipeline."""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, List
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


class LLMConfig(BaseSettings):
    """LLM configuration for content processing."""
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

    endpoint: str = "http://localhost:8080"
    model: str = "gpt-4"
    api_key: SecretStr = Field(default="", env="LLM_API_KEY")
    max_tokens: int = 1000
    temperature: float = 0.1
    max_concurrent_requests: int = 20
    request_timeout: float = 30.0
    retry_attempts: int = 3
    system_prompt: str = """You are a code analysis expert. Your task is to analyze code snippets and provide structured metadata.

Respond ONLY with valid JSON in this exact format:
{
    "language": "detected programming language",
    "title": "Brief, descriptive title (max 100 chars)",
    "description": "Comprehensive explanation including context, usage, and purpose (max 1000 chars)",
    "keywords": ["keyword1", "keyword2", ...],
    "frameworks": ["framework1", "framework2", ...],
    "purpose": "main purpose category",
    "dependencies": ["dependency1", "dependency2", ...]
}

Guidelines:
- Language detection is CRITICAL - use the full context including source URL to determine the correct language
- Language examples: javascript, typescript, python, java, go, rust, cpp, csharp, ruby, php, bash, yaml, json, xml, html, css
- For JSX code, use "javascript"; for TSX code, use "typescript"
- Title should be action-oriented and specific (e.g., "Bootstrap Next.js API Routes Middleware Example")
- Description should be comprehensive and include:
  * What the code does and its purpose
  * How to use it (if applicable)
  * Any prerequisites or setup required
  * Related concepts or alternatives mentioned in the context
  * Common use cases or scenarios
- When multiple similar code blocks exist (e.g., npm/yarn/pnpm), explain that users can choose their preferred option
- Keywords should include relevant technical terms, package names, and concepts
- Frameworks should list any frameworks/libraries used or referenced
- Purpose categories: authentication, database, api, ui, utility, configuration, testing, setup, initialization, etc.
- Dependencies are external libraries/modules imported or referenced"""


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
    tools: List[str] = ["init_crawl", "get_sources", "search_content"]


class CrawlingConfig(BaseSettings):
    """Web crawling configuration."""
    model_config = SettingsConfigDict(env_prefix="CRAWL_", extra="allow")

    default_max_depth: int = 2
    max_pages_per_job: int = 500
    respect_robots_txt: bool = True
    max_concurrent_pages: int = 3
    content_size_limit: int = 50000
    user_agent: str = "RAG-Pipeline/1.0 (Documentation Crawler)"
    max_concurrent_sessions: int = 20


class CodeExtractionConfig(BaseSettings):
    """Code extraction configuration."""
    model_config = SettingsConfigDict(env_prefix="CODE_", extra="allow")

    max_code_block_size: int = 50000
    preserve_context_chars: int = 500
    min_code_lines: int = 2
    extract_functions: bool = True
    extract_imports: bool = True
    detect_frameworks: bool = True
    supported_languages: List[str] = [
        "python", "javascript", "typescript", "java", "go", "rust",
        "cpp", "c", "csharp", "ruby", "php", "sql", "bash",
        "yaml", "json", "xml", "html", "css"
    ]


class SearchConfig(BaseSettings):
    """Search configuration."""
    model_config = SettingsConfigDict(env_prefix="SEARCH_", extra="allow")

    max_results: int = 50
    enable_fuzzy_search: bool = True
    boost_recent_days: int = 7
    snippet_preview_length: int = 200
    default_max_results: int = 10
    min_score: float = 0.1


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
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
        validate_assignment=True,
    )
    
    def __init__(self, **kwargs):
        """Initialize settings with sub-configurations."""
        super().__init__(**kwargs)
        
        # Initialize sub-configurations
        self.database = DatabaseConfig()
        self.llm = LLMConfig()
        self.mcp = MCPConfig()
        self.crawling = CrawlingConfig()
        self.code_extraction = CodeExtractionConfig()
        self.search = SearchConfig()
        self.api = APIConfig()
        self.logging = LoggingConfig()

    def setup_logging(self):
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
