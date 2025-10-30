import pytest

from src.config import Settings
from src.crawler.llm_retry import LLMDescriptionGenerator
from src.crawler.page_crawler import PageCrawler
from src.crawler.result_processor import ResultProcessor
from src.crawler.config import BrowserConfig
from src.runtime_settings import RuntimeSettingsManager
import src.runtime_settings as runtime_module


def test_llm_generator_property_access():
    generator = LLMDescriptionGenerator()
    
    settings1 = generator.settings
    settings2 = generator.settings
    
    assert settings1 is settings2
    assert isinstance(settings1.code_extraction.llm_extraction_model, str)


def test_llm_generator_hash_calculation():
    import os
    import src.config as config_module
    original_runtime = runtime_module._runtime_settings
    original_settings = config_module._settings
    
    try:
        runtime = RuntimeSettingsManager(config_path="test_component_hash.json")
        runtime_module._runtime_settings = runtime
        
        config_module._settings = None
        from src.config import get_settings
        settings = get_settings()
        
        runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
        settings.reload_runtime_overrides()
        
        generator = LLMDescriptionGenerator()
        hash1 = generator._get_settings_hash()
        
        runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
        settings.reload_runtime_overrides()
        hash2 = generator._get_settings_hash()
        
        assert hash1 != hash2
        
    finally:
        runtime_module._runtime_settings = original_runtime
        config_module._settings = original_settings
        if os.path.exists("test_component_hash.json"):
            os.remove("test_component_hash.json")


def test_llm_generator_change_detection():
    import os
    import src.config as config_module
    original_runtime = runtime_module._runtime_settings
    original_settings = config_module._settings
    
    try:
        runtime = RuntimeSettingsManager(config_path="test_component_change.json")
        runtime_module._runtime_settings = runtime
        
        config_module._settings = None
        from src.config import get_settings
        settings = get_settings()
        
        runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
        
        generator = LLMDescriptionGenerator()
        initial_hash = generator._last_settings_hash
        
        assert not generator._should_reinit_client()
        
        runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
        
        assert generator._should_reinit_client()
        assert generator._last_settings_hash != initial_hash
        
        assert not generator._should_reinit_client()
        
    finally:
        runtime_module._runtime_settings = original_runtime
        config_module._settings = original_settings
        if os.path.exists("test_component_change.json"):
            os.remove("test_component_change.json")


def test_page_crawler_property_access():
    browser_config = BrowserConfig()
    crawler = PageCrawler(browser_config)
    
    settings1 = crawler.settings
    settings2 = crawler.settings
    
    assert settings1 is settings2
    assert hasattr(settings1, 'crawling')


def test_result_processor_property_access():
    processor = ResultProcessor()
    
    settings1 = processor.settings
    settings2 = processor.settings
    
    assert settings1 is settings2
    assert hasattr(settings1, 'code_extraction')


def test_all_components_see_same_settings():
    generator = LLMDescriptionGenerator()
    browser_config = BrowserConfig()
    crawler = PageCrawler(browser_config)
    processor = ResultProcessor()
    
    gen_settings = generator.settings
    crawler_settings = crawler.settings
    processor_settings = processor.settings
    
    assert gen_settings is crawler_settings
    assert crawler_settings is processor_settings


def test_llm_generator_with_custom_settings():
    generator = LLMDescriptionGenerator(api_key="custom-key", model="custom-model")
    
    assert generator.custom_api_key == "custom-key"
    assert generator.custom_model == "custom-model"
    
    hash1 = generator._get_settings_hash()
    
    generator.custom_model = "different-model"
    
    hash2 = generator._get_settings_hash()
    assert hash1 != hash2
