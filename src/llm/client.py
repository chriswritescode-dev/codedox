"""LLM client for interacting with various LLM providers."""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class LLMError(Exception):
    """Base exception for LLM operations."""


class LLMConnectionError(LLMError):
    """Error connecting to LLM service."""


class LLMResponseError(LLMError):
    """Error in LLM response."""


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LLMClient:
    """Universal LLM client supporting multiple providers."""
    
    def __init__(self, 
                 endpoint: Optional[str] = None,
                 model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 timeout: float = 30.0,
                 max_retries: int = 3,
                 debug: bool = False):
        """Initialize LLM client.
        
        Args:
            endpoint: LLM API endpoint
            model: Model name to use
            api_key: API key for authentication
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            debug: Enable debug logging
        """
        settings = get_settings()
        
        # Use provided values or fall back to settings
        self.endpoint = endpoint or settings.llm.endpoint
        self.model = model or settings.llm.model
        self.api_key = api_key or settings.llm.api_key.get_secret_value()
        self.max_tokens = max_tokens or settings.llm.max_tokens
        self.temperature = temperature or settings.llm.temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug
        
        # Detect provider from endpoint
        self.provider = self._detect_provider()
        
        # HTTP client
        self.client = httpx.AsyncClient(timeout=self.timeout)
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(settings.llm.max_concurrent_requests)
        self._request_timeout = settings.llm.request_timeout
        self._retry_attempts = settings.llm.retry_attempts
        
        # Debug logging
        if self.debug:
            logger.setLevel(logging.DEBUG)
            
        logger.info(f"Initialized LLM client: provider={self.provider}, endpoint={self.endpoint}, model={self.model}, max_concurrent={settings.llm.max_concurrent_requests}")
    
    def _detect_provider(self) -> LLMProvider:
        """Detect LLM provider from endpoint."""
        endpoint_lower = self.endpoint.lower()
        
        if "openai.com" in endpoint_lower:
            return LLMProvider.OPENAI
        elif "anthropic.com" in endpoint_lower:
            return LLMProvider.ANTHROPIC
        elif "localhost" in endpoint_lower or "127.0.0.1" in endpoint_lower:
            # Check if it's Ollama
            if "11434" in self.endpoint:
                return LLMProvider.OLLAMA
            else:
                return LLMProvider.LOCAL
        else:
            return LLMProvider.CUSTOM
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to LLM service."""
        logger.info(f"Testing connection to {self.endpoint}")
        
        try:
            # Check if client is closed and recreate if needed
            if self.client.is_closed:
                logger.warning("LLM client was closed, recreating...")
                self.client = httpx.AsyncClient(timeout=self.timeout)
            
            # Different endpoints for different providers
            if self.provider == LLMProvider.OLLAMA:
                test_url = f"{self.endpoint}/api/tags"
            elif self.provider in [LLMProvider.OPENAI, LLMProvider.LOCAL, LLMProvider.CUSTOM]:
                # Try OpenAI-compatible endpoint
                test_url = f"{self.endpoint}/models"
            else:
                # Generic health check
                test_url = self.endpoint
            
            headers = self._get_headers()
            response = await self.client.get(test_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Connection successful: {data}")
                
                # Extract available models if present
                models = []
                if self.provider == LLMProvider.OLLAMA and "models" in data:
                    models = [m["name"] for m in data["models"]]
                elif "data" in data:  # OpenAI format
                    models = [m["id"] for m in data["data"]]
                
                return {
                    "status": "connected",
                    "provider": self.provider.value,
                    "endpoint": self.endpoint,
                    "models": models,
                    "response": data
                }
            else:
                logger.error(f"Connection test failed: {response.status_code} - {response.text}")
                return {
                    "status": "error",
                    "provider": self.provider.value,
                    "endpoint": self.endpoint,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except httpx.ConnectError as e:
            logger.error(f"Connection error: {e}")
            return {
                "status": "connection_error",
                "provider": self.provider.value,
                "endpoint": self.endpoint,
                "error": f"Cannot connect to {self.endpoint}: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error testing connection: {e}", exc_info=True)
            return {
                "status": "error",
                "provider": self.provider.value,
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request."""
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            if self.provider == LLMProvider.OPENAI:
                headers["Authorization"] = f"Bearer {self.api_key}"
            elif self.provider == LLMProvider.ANTHROPIC:
                headers["x-api-key"] = self.api_key
                headers["anthropic-version"] = "2023-06-01"
            elif self.provider in [LLMProvider.LOCAL, LLMProvider.CUSTOM]:
                # Try OpenAI-compatible auth
                headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    async def generate(self, 
                      prompt: str,
                      system_prompt: Optional[str] = None,
                      max_tokens: Optional[int] = None,
                      temperature: Optional[float] = None,
                      stream: bool = False) -> LLMResponse:
        """Generate text using LLM.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            max_tokens: Override default max tokens
            temperature: Override default temperature
            stream: Whether to stream response
            
        Returns:
            LLMResponse object
        """
        # Acquire semaphore to control concurrency
        async with self._semaphore:
            return await self._generate_with_timeout(
                prompt, system_prompt, max_tokens, temperature, stream
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError))
    )
    async def _generate_with_timeout(self,
                                   prompt: str,
                                   system_prompt: Optional[str] = None,
                                   max_tokens: Optional[int] = None,
                                   temperature: Optional[float] = None,
                                   stream: bool = False) -> LLMResponse:
        """Internal generate method with timeout."""
        start_time = time.time()
        
        # Check if client is closed and recreate if needed
        if self.client.is_closed:
            logger.warning("LLM client was closed, recreating...")
            self.client = httpx.AsyncClient(timeout=self.timeout)
        
        # Build request based on provider
        if self.provider == LLMProvider.OLLAMA:
            request_data = self._build_ollama_request(prompt, system_prompt, max_tokens, temperature)
            url = f"{self.endpoint}/api/generate"
        elif self.provider in [LLMProvider.OPENAI, LLMProvider.LOCAL, LLMProvider.CUSTOM]:
            request_data = self._build_openai_request(prompt, system_prompt, max_tokens, temperature)
            url = f"{self.endpoint}/chat/completions"
        elif self.provider == LLMProvider.ANTHROPIC:
            request_data = self._build_anthropic_request(prompt, system_prompt, max_tokens, temperature)
            url = f"{self.endpoint}/messages"
        else:
            raise LLMError(f"Unsupported provider: {self.provider}")
        
        headers = self._get_headers()
        
        if self.debug:
            logger.debug(f"LLM Request to {url}: {json.dumps(request_data, indent=2)}")
        
        try:
            response = await self.client.post(url, json=request_data, headers=headers)
            
            if response.status_code != 200:
                error_msg = f"LLM request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise LLMResponseError(error_msg)
            
            response_data = response.json()
            
            if self.debug:
                logger.debug(f"LLM Response: {json.dumps(response_data, indent=2)}")
            
            # Parse response based on provider
            llm_response = self._parse_response(response_data)
            
            # Add timing info
            llm_response.metadata["response_time"] = time.time() - start_time
            
            logger.info(f"Generated response: {len(llm_response.content)} chars in {llm_response.metadata['response_time']:.2f}s")
            
            return llm_response
            
        except httpx.ConnectError as e:
            error_msg = f"Failed to connect to LLM at {url}: {str(e)}"
            logger.error(error_msg)
            raise LLMConnectionError(error_msg) from e
        except httpx.TimeoutException as e:
            error_msg = f"LLM request timed out after {self.timeout}s"
            logger.error(error_msg)
            raise LLMConnectionError(error_msg) from e
        except Exception as e:
            logger.error(f"Unexpected error in LLM generation: {e}", exc_info=True)
            raise LLMError(f"LLM generation failed: {str(e)}") from e
    
    def _build_ollama_request(self, prompt: str, system_prompt: Optional[str], 
                             max_tokens: Optional[int], temperature: Optional[float]) -> Dict[str, Any]:
        """Build Ollama API request."""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        return {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens
            }
        }
    
    def _build_openai_request(self, prompt: str, system_prompt: Optional[str],
                             max_tokens: Optional[int], temperature: Optional[float]) -> Dict[str, Any]:
        """Build OpenAI-compatible API request."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "stream": False
        }
    
    def _build_anthropic_request(self, prompt: str, system_prompt: Optional[str],
                                max_tokens: Optional[int], temperature: Optional[float]) -> Dict[str, Any]:
        """Build Anthropic API request."""
        request_data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature
        }
        
        if system_prompt:
            request_data["system"] = system_prompt
        
        return request_data
    
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse LLM response based on provider format."""
        if self.provider == LLMProvider.OLLAMA:
            return LLMResponse(
                content=response_data.get("response", ""),
                model=response_data.get("model", self.model),
                usage={
                    "prompt_tokens": response_data.get("prompt_eval_count", 0),
                    "completion_tokens": response_data.get("eval_count", 0),
                    "total_tokens": response_data.get("prompt_eval_count", 0) + response_data.get("eval_count", 0)
                },
                metadata={
                    "provider": self.provider.value,
                    "eval_duration": response_data.get("eval_duration"),
                    "total_duration": response_data.get("total_duration")
                }
            )
        
        elif self.provider in [LLMProvider.OPENAI, LLMProvider.LOCAL, LLMProvider.CUSTOM]:
            # OpenAI-compatible format
            choice = response_data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            return LLMResponse(
                content=message.get("content", ""),
                model=response_data.get("model", self.model),
                usage=response_data.get("usage", {}),
                metadata={
                    "provider": self.provider.value,
                    "finish_reason": choice.get("finish_reason"),
                    "id": response_data.get("id")
                }
            )
        
        elif self.provider == LLMProvider.ANTHROPIC:
            content_blocks = response_data.get("content", [])
            content = " ".join([block.get("text", "") for block in content_blocks if block.get("type") == "text"])
            
            return LLMResponse(
                content=content,
                model=response_data.get("model", self.model),
                usage=response_data.get("usage", {}),
                metadata={
                    "provider": self.provider.value,
                    "id": response_data.get("id"),
                    "stop_reason": response_data.get("stop_reason")
                }
            )
        
        else:
            # Generic response parsing
            return LLMResponse(
                content=str(response_data),
                model=self.model,
                metadata={"provider": self.provider.value, "raw_response": response_data}
            )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()