# Settings Propagation Fix - Complete Implementation Plan

## Table of Contents
1. [Problem Statement](#problem-statement)
2. [Root Cause Analysis](#root-cause-analysis)
3. [Architecture Diagrams](#architecture-diagrams)
4. [Solution Design](#solution-design)
5. [Implementation Checklist](#implementation-checklist)
6. [Testing Strategy](#testing-strategy)
7. [Performance Analysis](#performance-analysis)
8. [Rollback Plan](#rollback-plan)

---

## Problem Statement

**Issue**: LLM settings configured via WebUI work correctly in the test endpoint but are NOT applied to actual crawling/extraction operations.

**Impact**: Users configure API keys and models via WebUI, test connection succeeds, but crawls still use old/default settings.

**Root Cause**: Components cache `get_settings()` at initialization and never reload when runtime config changes.

---

## Root Cause Analysis

### Current Architecture Issues

**1. Settings Caching**
```python
# Components cache settings at initialization
class LLMDescriptionGenerator:
    def __init__(self):
        self.settings = get_settings()  # ❌ Cached, never updates
```

**2. Component Lifecycle**
- Long-lived components persist across multiple operations
- LLM client initialized once with stale settings
- No mechanism to detect or react to settings changes

**3. Settings Flow Disconnect**
```
Runtime Update: config.runtime.json → RuntimeSettingsManager → Settings object
Component Access: Cached Settings → NEVER UPDATES ❌
Test Endpoint: Fresh get_settings() → ALWAYS WORKS ✓
```

### Files Affected

**Core Settings:**
- `src/config.py:23` - `self.settings = get_settings()`
- `src/runtime_settings.py` - No change notifications

**Components with Cached Settings:**
- `src/crawler/llm_retry.py:27` - `LLMDescriptionGenerator.__init__`
- `src/crawler/page_crawler.py:51` - `PageCrawler.__init__`
- `src/crawler/result_processor.py:23` - `ResultProcessor.__init__`

---

## Architecture Diagrams

### Current Flow (BROKEN)

```
┌─────────────────────────────────────┐
│      Application Startup            │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │  get_settings()      │
    │  Creates singleton   │
    └──────────┬───────────┘
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│PageCrawl│ │ LLMGen  │ │ResultProc│
│cached   │ │ cached  │ │ cached  │
└─────────┘ └─────────┘ └─────────┘
     │           │           │
     └───────────┴───────────┘
              │
         NEVER UPDATES ❌

┌─────────────────────────────────────┐
│      WebUI Settings Update          │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │ RuntimeSettings.set()│
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ Settings singleton   │
    │ _apply_overrides()   │
    └──────────────────────┘
               │
               X  NO PROPAGATION
               │
    Components still have old cache!
```

### New Flow (FIXED)

```
┌─────────────────────────────────────┐
│      Application Startup            │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │  get_settings()      │
    │  + Register observer │
    └──────────┬───────────┘
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│@property│ │@property│ │@property│
│settings │ │settings │ │settings │
└─────────┘ └─────────┘ └─────────┘
     │           │           │
     └───────────┴───────────┘
              │
      DYNAMIC ACCESS ✓

┌─────────────────────────────────────┐
│      WebUI Settings Update          │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │ RuntimeSettings.set()│
    │ _notify_observers()  │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ Settings.reload()    │
    │ _apply_overrides()   │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ Components access    │
    │ via @property        │
    │ Get fresh settings ✓ │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ LLM detects change   │
    │ Reinits client       │
    └──────────────────────┘
```

### Code Comparison

**BEFORE (Cached)**
```python
class LLMDescriptionGenerator:
    def __init__(self):
        self.settings = get_settings()  # ❌ Stale
    
    async def generate(self):
        api_key = self.settings.code_extraction.llm_api_key
```

**AFTER (Dynamic)**
```python
class LLMDescriptionGenerator:
    def __init__(self):
        self._last_settings_hash = None
    
    @property
    def settings(self):
        return get_settings()  # ✓ Always fresh
    
    async def generate(self):
        if self._should_reinit_client():
            self._init_client()
        api_key = self.settings.code_extraction.llm_api_key
```

---

## Solution Design

### Design Principles

1. **Single Source of Truth**: One global settings instance
2. **No Settings Caching**: Dynamic property access
3. **Lazy Evaluation**: Settings retrieved when needed
4. **Client Invalidation**: Reinit on change detection
5. **Backward Compatible**: Minimal API changes

### Implementation Strategy

#### 1. Observer Pattern (RuntimeSettingsManager)

```python
class RuntimeSettingsManager:
    def __init__(self):
        self._observers: list[callable] = []
    
    def add_observer(self, callback: callable) -> None:
        self._observers.append(callback)
    
    def _notify_observers(self) -> None:
        for callback in self._observers:
            try:
                callback()
            except Exception as e:
                logger.error(f"Observer error: {e}")
    
    def set(self, key: str, value: Any, category: str) -> None:
        # ... existing logic ...
        self._save()
        self._notify_observers()  # NEW
```

#### 2. Reload Mechanism (Settings)

```python
class Settings(BaseSettings):
    def reload_runtime_overrides(self) -> None:
        logger.info("Reloading runtime settings")
        self._apply_runtime_overrides()

def get_settings(force_reload: bool = False) -> Settings:
    global _settings
    if _settings is None or force_reload:
        _settings = Settings()
        _settings.setup_logging()
        
        # Register for changes
        runtime = get_runtime_settings()
        runtime.add_observer(_settings.reload_runtime_overrides)
    
    return _settings
```

#### 3. Dynamic Settings Access (Components)

```python
class LLMDescriptionGenerator:
    def __init__(self, api_key=None, base_url=None, model=None):
        # REMOVE: self.settings = get_settings()
        self.client = None
        self.custom_model = model
        self.custom_api_key = api_key
        self.custom_base_url = base_url
        self._last_settings_hash = None
        self._init_client()
    
    @property
    def settings(self):
        return get_settings()
    
    def _get_settings_hash(self) -> str:
        import hashlib
        settings = self.settings.code_extraction
        values = [
            str(settings.llm_api_key.get_secret_value()),
            str(settings.llm_base_url),
            str(settings.llm_extraction_model),
            str(settings.enable_llm_extraction),
        ]
        return hashlib.md5("".join(values).encode()).hexdigest()
    
    def _should_reinit_client(self) -> bool:
        current_hash = self._get_settings_hash()
        if current_hash != self._last_settings_hash:
            logger.info("LLM settings changed, reinitializing")
            self._last_settings_hash = current_hash
            return True
        return False
    
    async def generate_titles_and_descriptions_batch(self, ...):
        if self._should_reinit_client():
            self._init_client()
        # ... rest of method ...
```

#### 4. API Route Updates

```python
@router.put("/settings/{category}/{key}")
async def update_setting(category: str, key: str, request: UpdateSettingRequest):
    # ... validation ...
    runtime = get_runtime_settings()
    runtime.set(key, value, category)  # Triggers observer
    
    settings = get_settings()
    settings.reload_runtime_overrides()
    
    return {"message": f"Setting {key} updated"}
```

---

## Implementation Checklist

### Phase 1: Infrastructure (2-3 hours)

#### Step 1.1: Observer Pattern

**File**: `src/runtime_settings.py`

- [ ] Add `_observers: list[callable] = []` to `__init__`
- [ ] Add `add_observer(callback: callable)` method
- [ ] Add `_notify_observers()` method
- [ ] Call `_notify_observers()` in `set()`, `bulk_update()`, `reset()`
- [ ] Add logging for notifications

#### Step 1.2: Reload Mechanism

**File**: `src/config.py`

- [ ] Add `reload_runtime_overrides()` method to `Settings`
- [ ] Update `get_settings()` to register observer
- [ ] Add reload logging

#### Step 1.3: Infrastructure Tests

**File**: `tests/test_settings_infrastructure.py`

- [ ] Test observer registration
- [ ] Test observer notification
- [ ] Test settings reload
- [ ] Test error handling

---

### Phase 2: Component Refactoring (3-4 hours)

#### Step 2.1: LLMDescriptionGenerator

**File**: `src/crawler/llm_retry.py`

- [ ] Remove `self.settings = get_settings()`
- [ ] Add `@property` for settings
- [ ] Add `_last_settings_hash`
- [ ] Add `_get_settings_hash()` method
- [ ] Add `_should_reinit_client()` method
- [ ] Update `_init_client()` to track hash
- [ ] Add check in `generate_titles_and_descriptions_batch()`

#### Step 2.2: PageCrawler

**File**: `src/crawler/page_crawler.py`

- [ ] Remove `self.settings = get_settings()`
- [ ] Add `@property` for settings
- [ ] Verify all `self.settings` accesses work

#### Step 2.3: ResultProcessor

**File**: `src/crawler/result_processor.py`

- [ ] Remove `self.settings = get_settings()`
- [ ] Add `@property` for settings
- [ ] Verify all `self.settings` accesses work

#### Step 2.4: Component Tests

**File**: `tests/test_component_settings.py`

- [ ] Test LLMDescriptionGenerator property access
- [ ] Test PageCrawler property access
- [ ] Test ResultProcessor property access
- [ ] Test hash-based change detection

---

### Phase 3: API Integration (2-3 hours)

#### Step 3.1: Update API Routes

**File**: `src/api/routes/runtime_settings.py`

- [ ] Update `update_setting()` to trigger reload
- [ ] Update `bulk_update_settings()` to trigger reload
- [ ] Update `reset_setting()` to trigger reload

#### Step 3.2: Integration Tests

**File**: `tests/test_settings_integration.py`

- [ ] Test API update propagates to components
- [ ] Test LLM client reinitializes on change
- [ ] Test mid-crawl settings update
- [ ] Test bulk update
- [ ] Test reset

#### Step 3.3: Manual Testing

- [ ] Start app: `python cli.py serve`
- [ ] Configure LLM settings via WebUI
- [ ] Test connection (should succeed)
- [ ] Start crawl
- [ ] Verify LLM used (check logs)
- [ ] Update model mid-crawl
- [ ] Verify new model used
- [ ] Reset settings
- [ ] Verify defaults applied

---

### Phase 4: Performance Validation (1 hour)

- [ ] Benchmark property access vs cached (~40ns expected)
- [ ] Benchmark hash calculation (~1-2ms expected)
- [ ] Benchmark client reinit (~50-100ms expected)
- [ ] Verify total overhead < 2%

---

### Phase 5: Documentation (1 hour)

- [ ] Update CLAUDE.md with new architecture
- [ ] Add troubleshooting section
- [ ] Document observer pattern
- [ ] Add code comments

---

## Testing Strategy

### Unit Tests

```python
# tests/test_settings_infrastructure.py

def test_observer_notification():
    called = False
    def callback():
        nonlocal called
        called = True
    
    runtime = get_runtime_settings()
    runtime.add_observer(callback)
    runtime.set("CODE_LLM_API_KEY", "test", "llm")
    
    assert called

def test_settings_property_access():
    gen = LLMDescriptionGenerator()
    s1 = gen.settings
    s2 = gen.settings
    assert s1 is s2  # Same singleton

def test_hash_change_detection():
    gen = LLMDescriptionGenerator()
    initial = gen._get_settings_hash()
    
    runtime = get_runtime_settings()
    runtime.set("CODE_LLM_EXTRACTION_MODEL", "gpt-4", "llm")
    
    new = gen._get_settings_hash()
    assert initial != new
    assert gen._should_reinit_client()
```

### Integration Tests

```python
# tests/test_settings_integration.py

async def test_settings_propagate_to_llm():
    runtime = get_runtime_settings()
    runtime.set("CODE_LLM_API_KEY", "key1", "llm")
    
    gen = LLMDescriptionGenerator()
    assert gen.settings.code_extraction.llm_api_key.get_secret_value() == "key1"
    
    runtime.set("CODE_LLM_API_KEY", "key2", "llm")
    assert gen.settings.code_extraction.llm_api_key.get_secret_value() == "key2"

async def test_api_update_triggers_reload():
    response = await client.put("/api/settings/llm/CODE_LLM_API_KEY", 
                                 json={"value": "new-key"})
    assert response.status_code == 200
    
    gen = LLMDescriptionGenerator()
    assert gen.settings.code_extraction.llm_api_key.get_secret_value() == "new-key"
```

### Manual Test Scenarios

**Scenario 1: Cold Start**
1. Delete `config.runtime.json`
2. Start app
3. Configure settings via WebUI
4. Start crawl
5. Verify settings used in logs

**Scenario 2: Hot Reload**
1. Start app with settings
2. Start crawl
3. Update settings mid-crawl
4. Verify new settings used for new pages

**Scenario 3: Settings Reset**
1. Configure custom settings
2. Start crawl
3. Reset to defaults
4. Verify defaults used

---

## Performance Analysis

### Property Access Overhead

```
Cached:   self.settings.x     ~10ns
Dynamic:  self.settings.x     ~50ns (property call + singleton)
Overhead: ~40ns per access (negligible)
```

### Hash Calculation

```
Per batch operation:
  - MD5 hash of 4 strings: ~1-2ms
  - Comparison: ~0.001ms
  - Reinit (if changed): ~50-100ms (rare)
Total: ~1-2ms per batch
```

### Expected Impact

- **Property access**: < 0.1% overhead
- **Change detection**: < 0.5% overhead
- **Client reinit**: Only on actual changes
- **Total**: < 2% overall

---

## Rollback Plan

### If Critical Issues Occur:

**Option 1: Git Revert**
```bash
git revert <commit-hash>
git push
```

**Option 2: Feature Flag**
```python
# Add to .env
ENABLE_DYNAMIC_SETTINGS=false

# In get_settings()
if not os.getenv("ENABLE_DYNAMIC_SETTINGS", "true").lower() == "true":
    return _cached_settings
```

**Option 3: Partial Rollback**
- Keep observer pattern
- Disable auto-reload
- Require manual API call to reload

---

## Success Criteria

- [ ] LLM settings updated via WebUI apply immediately
- [ ] All existing tests pass
- [ ] New tests pass (unit, integration, manual)
- [ ] Performance overhead < 2%
- [ ] No breaking changes to existing code
- [ ] Documentation updated

---

## Timeline

- **Phase 1**: 2-3 hours (infrastructure)
- **Phase 2**: 3-4 hours (components)
- **Phase 3**: 2-3 hours (API & testing)
- **Phase 4**: 1 hour (performance)
- **Phase 5**: 1 hour (docs)
- **Total**: 7-10 hours

---

## Risk Assessment

**Low Risk:**
- Observer pattern (additive)
- Reload method (opt-in)
- Documentation

**Medium Risk:**
- Component refactoring (behavior change)
- Property access (performance impact)

**Mitigation:**
- Comprehensive tests
- Performance benchmarks
- Feature flag option
- Gradual rollout

---

## Files Changed Summary

**Core (2 files)**
- `src/runtime_settings.py` - Observer pattern
- `src/config.py` - Reload mechanism

**Components (3 files)**
- `src/crawler/llm_retry.py` - Dynamic settings + change detection
- `src/crawler/page_crawler.py` - Dynamic settings
- `src/crawler/result_processor.py` - Dynamic settings

**API (1 file)**
- `src/api/routes/runtime_settings.py` - Trigger reload

**Tests (3 files)**
- `tests/test_settings_infrastructure.py` - New
- `tests/test_component_settings.py` - New
- `tests/test_settings_integration.py` - New

---

**Status**: Ready for Implementation
**Created**: 2025-10-29
**Estimated Completion**: 7-10 hours
