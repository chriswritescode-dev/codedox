import os
import pytest

from src.config import Settings, get_settings
from src.crawler.llm_retry import LLMDescriptionGenerator
from src.runtime_settings import RuntimeSettingsManager
import src.runtime_settings as runtime_module
import src.config as config_module


@pytest.fixture
def isolated_runtime():
    original_runtime = runtime_module._runtime_settings
    original_settings = config_module._settings
    
    runtime = RuntimeSettingsManager(config_path="test_integration.json")
    runtime_module._runtime_settings = runtime
    
    config_module._settings = None
    settings = get_settings()
    
    yield runtime, settings
    
    runtime_module._runtime_settings = original_runtime
    config_module._settings = original_settings
    
    if os.path.exists("test_integration.json"):
        os.remove("test_integration.json")


def test_settings_propagate_via_observer(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
    
    assert settings.code_extraction.llm_extraction_model == "gpt-4o-mini"
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
    
    assert settings.code_extraction.llm_extraction_model == "gpt-4"


def test_llm_generator_sees_runtime_changes(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
    
    generator = LLMDescriptionGenerator()
    
    assert generator.settings.code_extraction.llm_extraction_model == "gpt-4o-mini"
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
    
    assert generator.settings.code_extraction.llm_extraction_model == "gpt-4"


def test_llm_client_reinitializes_on_change(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
    runtime.set("CODE_LLM_API_KEY", "test-key-1", "llm")
    
    generator = LLMDescriptionGenerator()
    hash1 = generator._last_settings_hash
    
    assert not generator._should_reinit_client()
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
    
    should_reinit = generator._should_reinit_client()
    assert should_reinit
    
    hash2 = generator._last_settings_hash
    assert hash1 != hash2


def test_bulk_update_propagates(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.bulk_update({
        "llm": {
            "CODE_LLM_EXTRACTION_MODEL": "gpt-4",
            "CODE_LLM_MAX_TOKENS": 2000,
        }
    })
    
    assert settings.code_extraction.llm_extraction_model == "gpt-4"
    assert settings.code_extraction.llm_max_tokens == 2000


def test_reset_propagates(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "custom-model", "llm")
    assert settings.code_extraction.llm_extraction_model == "custom-model"
    
    original_count = len([obs for obs in runtime._observers])
    
    runtime.reset("CODE_LLM_EXTRACTION_MODEL", "llm")
    
    refreshed_model = settings.code_extraction.llm_extraction_model
    
    assert refreshed_model != "custom-model"
    assert len([obs for obs in runtime._observers]) == original_count


def test_multiple_components_see_same_updated_settings(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
    
    gen1 = LLMDescriptionGenerator()
    gen2 = LLMDescriptionGenerator()
    
    assert gen1.settings.code_extraction.llm_extraction_model == "gpt-4o-mini"
    assert gen2.settings.code_extraction.llm_extraction_model == "gpt-4o-mini"
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
    
    assert gen1.settings.code_extraction.llm_extraction_model == "gpt-4"
    assert gen2.settings.code_extraction.llm_extraction_model == "gpt-4"
    
    assert gen1.settings is gen2.settings


def test_observer_called_on_each_change(isolated_runtime):
    runtime, settings = isolated_runtime
    
    call_count = [0]
    
    def counting_callback():
        call_count[0] += 1
    
    runtime.add_observer(counting_callback)
    
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
    assert call_count[0] == 1
    
    runtime.set("CODE_LLM_MAX_TOKENS", 2000, "llm")
    assert call_count[0] == 2
    
    runtime.bulk_update({"llm": {"CODE_LLM_EXTRACTION_MODEL": "gpt-4o-mini"}})
    assert call_count[0] == 3
    
    runtime.reset("CODE_LLM_EXTRACTION_MODEL", "llm")
    assert call_count[0] == 4


def test_settings_hash_changes_with_api_key(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_API_KEY", "key1", "llm")
    
    generator = LLMDescriptionGenerator()
    hash1 = generator._get_settings_hash()
    
    runtime.set("CODE_LLM_API_KEY", "key2", "llm")
    hash2 = generator._get_settings_hash()
    
    assert hash1 != hash2


def test_settings_hash_changes_with_base_url(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_LLM_BASE_URL", "http://localhost:8000", "llm")
    
    generator = LLMDescriptionGenerator()
    hash1 = generator._get_settings_hash()
    
    runtime.set("CODE_LLM_BASE_URL", "http://localhost:9000", "llm")
    hash2 = generator._get_settings_hash()
    
    assert hash1 != hash2


def test_settings_hash_changes_with_enable_flag(isolated_runtime):
    runtime, settings = isolated_runtime
    
    runtime.set("CODE_ENABLE_LLM_EXTRACTION", True, "llm")
    
    generator = LLMDescriptionGenerator()
    hash1 = generator._get_settings_hash()
    
    runtime.set("CODE_ENABLE_LLM_EXTRACTION", False, "llm")
    hash2 = generator._get_settings_hash()
    
    assert hash1 != hash2
