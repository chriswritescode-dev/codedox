import pytest

from src.config import Settings, get_settings
from src.runtime_settings import RuntimeSettingsManager, get_runtime_settings


def test_observer_registration():
    runtime = RuntimeSettingsManager(config_path="test_config_observer.json")
    
    called = False
    
    def callback():
        nonlocal called
        called = True
    
    runtime.add_observer(callback)
    assert callback in runtime._observers
    
    import os
    if os.path.exists("test_config_observer.json"):
        os.remove("test_config_observer.json")


def test_observer_notification_on_set():
    runtime = RuntimeSettingsManager(config_path="test_config_set.json")
    
    call_count = 0
    
    def callback():
        nonlocal call_count
        call_count += 1
    
    runtime.add_observer(callback)
    runtime.set("CODE_LLM_API_KEY", "test-key", "llm")
    
    assert call_count == 1
    
    import os
    if os.path.exists("test_config_set.json"):
        os.remove("test_config_set.json")


def test_observer_notification_on_bulk_update():
    runtime = RuntimeSettingsManager(config_path="test_config_bulk.json")
    
    call_count = 0
    
    def callback():
        nonlocal call_count
        call_count += 1
    
    runtime.add_observer(callback)
    runtime.bulk_update({
        "llm": {"CODE_LLM_API_KEY": "key1", "CODE_LLM_EXTRACTION_MODEL": "gpt-4"}
    })
    
    assert call_count == 1
    
    import os
    if os.path.exists("test_config_bulk.json"):
        os.remove("test_config_bulk.json")


def test_observer_notification_on_reset():
    runtime = RuntimeSettingsManager(config_path="test_config_reset.json")
    
    call_count = 0
    
    def callback():
        nonlocal call_count
        call_count += 1
    
    runtime.set("CODE_LLM_API_KEY", "test-key", "llm")
    runtime.add_observer(callback)
    runtime.reset("CODE_LLM_API_KEY", "llm")
    
    assert call_count == 1
    
    import os
    if os.path.exists("test_config_reset.json"):
        os.remove("test_config_reset.json")


def test_observer_error_handling():
    runtime = RuntimeSettingsManager(config_path="test_config_error.json")
    
    def broken_callback():
        raise Exception("Test error")
    
    def working_callback():
        pass
    
    runtime.add_observer(broken_callback)
    runtime.add_observer(working_callback)
    
    runtime.set("CODE_LLM_API_KEY", "test-key", "llm")
    
    import os
    if os.path.exists("test_config_error.json"):
        os.remove("test_config_error.json")


def test_settings_reload_method_exists():
    settings = Settings()
    assert hasattr(settings, 'reload_runtime_overrides')
    assert callable(settings.reload_runtime_overrides)


def test_settings_reload_applies_changes():
    import os
    import src.runtime_settings as runtime_module
    
    original_runtime = runtime_module._runtime_settings
    
    try:
        runtime = RuntimeSettingsManager(config_path="test_config_reload.json")
        runtime_module._runtime_settings = runtime
        
        runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4o-mini", "llm")
        
        settings = Settings()
        
        assert settings.code_extraction.llm_extraction_model == "gpt-4o-mini"
        
        runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
        settings.reload_runtime_overrides()
        
        assert settings.code_extraction.llm_extraction_model == "gpt-4"
        
    finally:
        runtime_module._runtime_settings = original_runtime
        if os.path.exists("test_config_reload.json"):
            os.remove("test_config_reload.json")


def test_multiple_observers():
    runtime = RuntimeSettingsManager(config_path="test_config_multi.json")
    
    calls = []
    
    def callback1():
        calls.append(1)
    
    def callback2():
        calls.append(2)
    
    def callback3():
        calls.append(3)
    
    runtime.add_observer(callback1)
    runtime.add_observer(callback2)
    runtime.add_observer(callback3)
    
    runtime.set("CODE_LLM_API_KEY", "test-key", "llm")
    
    assert len(calls) == 3
    assert 1 in calls
    assert 2 in calls
    assert 3 in calls
    
    import os
    if os.path.exists("test_config_multi.json"):
        os.remove("test_config_multi.json")


def test_observer_not_duplicated():
    runtime = RuntimeSettingsManager(config_path="test_config_dup.json")
    
    call_count = 0
    
    def callback():
        nonlocal call_count
        call_count += 1
    
    runtime.add_observer(callback)
    runtime.add_observer(callback)
    runtime.add_observer(callback)
    
    assert runtime._observers.count(callback) == 1
    
    runtime.set("CODE_LLM_API_KEY", "test-key", "llm")
    assert call_count == 1
    
    import os
    if os.path.exists("test_config_dup.json"):
        os.remove("test_config_dup.json")
