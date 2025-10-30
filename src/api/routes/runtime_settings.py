import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config import get_settings
from ...runtime_settings import get_runtime_settings

logger = logging.getLogger(__name__)
router = APIRouter()


SETTING_METADATA = {
    "llm": {
        "CODE_ENABLE_LLM_EXTRACTION": {
            "type": "boolean",
            "description": "Enable AI-powered code extraction",
            "default": False,
        },
        "CODE_LLM_API_KEY": {
            "type": "secret",
            "description": "OpenAI-compatible API key",
            "default": "",
        },
        "CODE_LLM_BASE_URL": {
            "type": "url",
            "description": "Custom LLM endpoint URL (optional)",
            "default": None,
        },
        "CODE_LLM_EXTRACTION_MODEL": {
            "type": "select",
            "description": "Model name for extraction",
            "default": "gpt-4o-mini",
            "dynamic_options": True,
        },
        "CODE_LLM_MAX_TOKENS": {
            "type": "integer",
            "description": "Max tokens for generation",
            "default": 1000,
            "min": 100,
            "max": 10000,
        },
        "CODE_LLM_EXTRA_PARAMS": {
            "type": "json",
            "description": "Custom JSON parameters for LLM requests (e.g., {\"temperature\": 0.7, \"extra_body\": {\"chat_template_kwargs\": {\"enable_thinking\": false}}})",
            "default": "{}",
        },
    },
    "crawling": {
        "CRAWL_MAX_CONCURRENT_CRAWLS": {
            "type": "integer",
            "description": "Max concurrent crawl sessions per job",
            "default": 5,
            "min": 1,
            "max": 50,
        },
        "CRAWL_MAX_CONCURRENT_PAGES": {
            "type": "integer",
            "description": "Max concurrent page fetches",
            "default": 3,
            "min": 1,
            "max": 10,
        },
        "CRAWL_DEFAULT_MAX_DEPTH": {
            "type": "integer",
            "description": "Default crawl depth",
            "default": 2,
            "min": 0,
            "max": 5,
        },
        "CRAWL_CONTENT_SIZE_LIMIT": {
            "type": "integer",
            "description": "Max content size in bytes",
            "default": 50000,
            "min": 10000,
            "max": 500000,
        },
        "CRAWL_RESPECT_ROBOTS_TXT": {
            "type": "boolean",
            "description": "Respect robots.txt",
            "default": True,
        },
    },
    "search": {
        "SEARCH_MAX_RESULTS": {
            "type": "integer",
            "description": "Maximum search results",
            "default": 50,
            "min": 10,
            "max": 500,
        },
        "SEARCH_ENABLE_FUZZY_SEARCH": {
            "type": "boolean",
            "description": "Enable fuzzy matching",
            "default": True,
        },
        "SEARCH_MIN_SCORE": {
            "type": "float",
            "description": "Minimum match score",
            "default": 0.1,
            "min": 0.0,
            "max": 1.0,
        },
        "SEARCH_MARKDOWN_FALLBACK_ENABLED": {
            "type": "boolean",
            "description": "Enable markdown fallback search",
            "default": True,
        },
        "SEARCH_MARKDOWN_FALLBACK_THRESHOLD": {
            "type": "integer",
            "description": "Trigger threshold for fallback",
            "default": 5,
            "min": 1,
            "max": 50,
        },
    },
    "security": {
        "MCP_AUTH_ENABLED": {
            "type": "boolean",
            "description": "Enable MCP authentication",
            "default": False,
        },
        "MCP_AUTH_TOKEN": {
            "type": "secret",
            "description": "MCP authentication token",
            "default": "",
        },
    },
    "api": {
        "API_CORS_ORIGINS": {
            "type": "string",
            "description": "Comma-separated CORS origins",
            "default": "http://localhost:3000,http://localhost:5173,http://localhost:8000",
        },
        "API_MAX_REQUEST_SIZE": {
            "type": "integer",
            "description": "Max request size in bytes (10MB)",
            "default": 10485760,
            "min": 1048576,
            "max": 104857600,
        },
    },
    "advanced": {
        "UPLOAD_MAX_FILE_SIZE": {
            "type": "integer",
            "description": "Max upload file size in bytes (10MB)",
            "default": 10485760,
            "min": 1048576,
            "max": 104857600,
        },
        "LOG_LEVEL": {
            "type": "string",
            "description": "Logging level",
            "default": "INFO",
            "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    },
}


class UpdateSettingRequest(BaseModel):
    value: Any = Field(..., description="New value for the setting")


class BulkUpdateRequest(BaseModel):
    updates: dict[str, dict[str, Any]] = Field(
        ..., description="Category-grouped settings to update"
    )


def _mask_secret(value: str) -> str:
    if not value or len(value) < 8:
        return "••••••••"
    return "•" * (len(value) - 4) + value[-4:]


def _get_current_value(category: str, key: str) -> Any:
    runtime = get_runtime_settings()
    runtime_value = runtime.get(key, category)
    if runtime_value is not None:
        return runtime_value

    settings = get_settings()
    
    config_map = {
        "llm": ("code_extraction", "CODE_"),
        "crawling": ("crawling", "CRAWL_"),
        "search": ("search", "SEARCH_"),
        "security": ("mcp_auth", "MCP_AUTH_"),
        "api": ("api", "API_"),
    }
    
    if category == "advanced":
        if key.startswith("UPLOAD_"):
            attr_name = key.replace("UPLOAD_", "").lower()
            return getattr(settings.upload, attr_name, None)
        elif key.startswith("LOG_"):
            attr_name = key.replace("LOG_", "").lower()
            return getattr(settings.logging, attr_name, None)
    
    if category in config_map:
        config_name, prefix = config_map[category]
        config_obj = getattr(settings, config_name)
        attr_name = key.replace(prefix, "").lower()
        value = getattr(config_obj, attr_name, None)
        
        if hasattr(value, 'get_secret_value'):
            return value.get_secret_value()
        return value
    
    return None


@router.get("/settings")
async def get_all_settings() -> dict[str, Any]:
    runtime = get_runtime_settings()
    runtime_overrides = runtime.get_all()
    
    result = {}
    
    for category, settings_dict in SETTING_METADATA.items():
        result[category] = []
        
        for key, metadata in settings_dict.items():
            current_value = _get_current_value(category, key)
            is_modified = key in runtime_overrides.get(category, {})
            
            display_value = current_value
            if metadata["type"] == "secret" and current_value:
                display_value = _mask_secret(str(current_value))
            
            result[category].append({
                "key": key,
                "value": display_value,
                "default_value": metadata.get("default"),
                "type": metadata["type"],
                "description": metadata["description"],
                "is_modified": is_modified,
                "options": metadata.get("options"),
                "min": metadata.get("min"),
                "max": metadata.get("max"),
            })
    
    return result


@router.get("/settings/{category}/{key}")
async def get_setting(category: str, key: str) -> dict[str, Any]:
    if category not in SETTING_METADATA or key not in SETTING_METADATA[category]:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    metadata = SETTING_METADATA[category][key]
    current_value = _get_current_value(category, key)
    
    runtime = get_runtime_settings()
    runtime_overrides = runtime.get_all()
    is_modified = key in runtime_overrides.get(category, {})
    
    display_value = current_value
    if metadata["type"] == "secret" and current_value:
        display_value = _mask_secret(str(current_value))
    
    return {
        "key": key,
        "value": display_value,
        "default_value": metadata.get("default"),
        "category": category,
        "type": metadata["type"],
        "description": metadata["description"],
        "is_modified": is_modified,
        "options": metadata.get("options"),
        "min": metadata.get("min"),
        "max": metadata.get("max"),
    }


@router.put("/settings/{category}/{key}")
async def update_setting(
    category: str, key: str, request: UpdateSettingRequest
) -> dict[str, str]:
    if category not in SETTING_METADATA or key not in SETTING_METADATA[category]:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    metadata = SETTING_METADATA[category][key]
    value = request.value
    
    if metadata["type"] == "integer":
        if not isinstance(value, int):
            raise HTTPException(status_code=400, detail="Value must be an integer")
        if "min" in metadata and value < metadata["min"]:
            raise HTTPException(status_code=400, detail=f"Value must be >= {metadata['min']}")
        if "max" in metadata and value > metadata["max"]:
            raise HTTPException(status_code=400, detail=f"Value must be <= {metadata['max']}")
    
    elif metadata["type"] == "float":
        if not isinstance(value, (int, float)):
            raise HTTPException(status_code=400, detail="Value must be a number")
        if "min" in metadata and value < metadata["min"]:
            raise HTTPException(status_code=400, detail=f"Value must be >= {metadata['min']}")
        if "max" in metadata and value > metadata["max"]:
            raise HTTPException(status_code=400, detail=f"Value must be <= {metadata['max']}")
    
    elif metadata["type"] == "boolean":
        if not isinstance(value, bool):
            raise HTTPException(status_code=400, detail="Value must be a boolean")
    
    elif metadata["type"] == "string":
        if not isinstance(value, str):
            raise HTTPException(status_code=400, detail="Value must be a string")
        if "options" in metadata and value not in metadata["options"]:
            raise HTTPException(
                status_code=400, detail=f"Value must be one of: {', '.join(metadata['options'])}"
            )
    
    elif metadata["type"] == "json":
        if isinstance(value, str):
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
        elif not isinstance(value, dict):
            raise HTTPException(status_code=400, detail="Value must be a JSON string or object")
    
    runtime = get_runtime_settings()
    runtime.set(key, value, category)
    
    settings = get_settings()
    settings._apply_runtime_overrides()
    
    return {"message": f"Setting {key} updated successfully"}


@router.delete("/settings/{category}/{key}")
async def reset_setting(category: str, key: str) -> dict[str, str]:
    if category not in SETTING_METADATA or key not in SETTING_METADATA[category]:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    runtime = get_runtime_settings()
    runtime.reset(key, category)
    
    settings = get_settings()
    settings._apply_runtime_overrides()
    
    return {"message": f"Setting {key} reset to default"}


@router.post("/settings/bulk")
async def bulk_update_settings(request: BulkUpdateRequest) -> dict[str, str]:
    runtime = get_runtime_settings()
    runtime.bulk_update(request.updates)
    
    settings = get_settings()
    settings._apply_runtime_overrides()
    
    return {"message": "Settings updated successfully"}


@router.post("/settings/reload")
async def reload_settings() -> dict[str, str]:
    runtime = get_runtime_settings()
    runtime.reload()
    
    settings = get_settings()
    settings._apply_runtime_overrides()
    
    return {"message": "Settings reloaded successfully"}


class TestLLMRequest(BaseModel):
    api_key: str | None = Field(None, description="API key to test (optional, uses .env if not provided)")
    base_url: str | None = Field(None, description="Base URL (optional)")
    model: str = Field(default="gpt-4o-mini", description="Model name")
    max_tokens: int | None = Field(None, description="Max tokens (optional, uses settings if not provided)")
    extra_params: str = Field(default="{}", description="Extra parameters JSON")


@router.get("/settings/list-models")
async def list_available_models() -> dict[str, Any]:
    try:
        from openai import OpenAI
        
        settings = get_settings()
        api_key = settings.code_extraction.llm_api_key.get_secret_value()
        
        if not api_key:
            return {
                "status": "error",
                "message": "No API key configured",
                "models": []
            }
        
        base_url = settings.code_extraction.llm_base_url
        
        client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None,
        )
        
        models_response = client.models.list()
        models = [model.id for model in models_response.data]
        
        return {
            "status": "success",
            "models": sorted(models),
            "count": len(models)
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return {
            "status": "error",
            "message": str(e),
            "models": []
        }


@router.post("/settings/test-llm")
async def test_llm_connection(request: TestLLMRequest) -> dict[str, Any]:
    import time

    try:
        from openai import OpenAI
        
        start_time = time.time()
        
        # Use provided API key or fall back to settings
        api_key = request.api_key
        if not api_key or '••••' in api_key:
            settings = get_settings()
            api_key = settings.code_extraction.llm_api_key.get_secret_value()
        
        if not api_key:
            return {
                "status": "error",
                "message": "No API key configured. Please set CODE_LLM_API_KEY in .env or provide one in settings.",
                "error": "Missing API key",
            }
        
        client = OpenAI(
            api_key=api_key,
            base_url=request.base_url if request.base_url else None,
        )
        
        # Parse extra parameters
        extra_params = {}
        try:
            if request.extra_params and request.extra_params != "{}":
                extra_params = json.loads(request.extra_params)
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": "Invalid JSON in extra parameters",
                "error": str(e),
            }
        
        # Get max_tokens from request or fall back to settings
        max_tokens = request.max_tokens
        if max_tokens is None:
            settings = get_settings()
            max_tokens = settings.code_extraction.llm_max_tokens
        
        # Build request parameters with simple test message using exact settings
        request_params = {
            "model": request.model,
            "messages": [{"role": "user", "content": "Are you ready?"}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        request_params.update(extra_params)
        
        response = client.chat.completions.create(**request_params)
        
        elapsed_time = time.time() - start_time
        
        # Parse response
        message = response.choices[0].message
        content = message.content
        finish_reason = response.choices[0].finish_reason
        
        # Check for reasoning content (DeepSeek R1 style models)
        reasoning_content = None
        if hasattr(message, 'reasoning_content'):
            reasoning_content = message.reasoning_content
        
        # Build response message
        if content:
            response_text = content
        elif reasoning_content:
            response_text = f"[No content - reasoning only: {reasoning_content[:100]}...]"
        else:
            response_text = "[No response content]"
        
        return {
            "status": "success",
            "message": f"Model: {response.model}\nLatency: {int(elapsed_time * 1000)}ms\nResponse: {response_text}",
            "model": response.model,
            "latency_ms": int(elapsed_time * 1000),
            "response": response_text,
            "finish_reason": finish_reason,
        }
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
            return {
                "status": "error",
                "message": "Authentication failed - invalid API key",
                "error": error_msg,
            }
        elif "not found" in error_msg.lower() or "model" in error_msg.lower():
            return {
                "status": "error",
                "message": f"Model '{request.model}' not found or not accessible",
                "error": error_msg,
            }
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return {
                "status": "error",
                "message": "Connection failed - check base URL and network",
                "error": error_msg,
            }
        else:
            return {
                "status": "error",
                "message": "LLM connection failed",
                "error": error_msg,
            }
