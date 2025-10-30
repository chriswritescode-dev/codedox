import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class RuntimeSettingsManager:
    def __init__(self, config_path: str = "config.runtime.json"):
        self.config_path = Path(config_path)
        self._lock = Lock()
        self._settings: dict[str, dict[str, Any]] = {}
        self._observers: list[Callable[[], None]] = []
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            logger.info(f"Runtime config file not found: {self.config_path}, using defaults")
            self._settings = {}
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self._settings = {k: v for k, v in data.items() if k != "metadata"}
                logger.info(f"Loaded runtime settings from {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse runtime config: {e}, using defaults")
            self._settings = {}
        except Exception as e:
            logger.error(f"Failed to load runtime config: {e}, using defaults")
            self._settings = {}

    def _save(self) -> None:
        with self._lock:
            backup_path = self.config_path.with_suffix(".json.bak")
            
            if self.config_path.exists():
                self.config_path.rename(backup_path)

            try:
                data = dict(self._settings)
                data["metadata"] = {
                    "last_updated": datetime.utcnow().isoformat(),
                    "version": "1.0"
                }
                
                temp_path = self.config_path.with_suffix(".json.tmp")
                with open(temp_path, "w") as f:
                    json.dump(data, f, indent=2)
                
                os.chmod(temp_path, 0o600)
                temp_path.rename(self.config_path)
                
                if backup_path.exists():
                    backup_path.unlink()
                    
                logger.info(f"Saved runtime settings to {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to save runtime config: {e}")
                if backup_path.exists():
                    backup_path.rename(self.config_path)
                raise

    def get(self, key: str, category: str | None = None) -> Any | None:
        with self._lock:
            if category:
                return self._settings.get(category, {}).get(key)
            
            for cat_settings in self._settings.values():
                if isinstance(cat_settings, dict) and key in cat_settings:
                    return cat_settings[key]
            return None

    def add_observer(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if callback not in self._observers:
                self._observers.append(callback)
                logger.info(f"Added settings observer: {callback.__name__}")
    
    def _notify_observers(self) -> None:
        for callback in self._observers:
            try:
                callback()
                logger.debug(f"Notified observer: {callback.__name__}")
            except Exception as e:
                logger.error(f"Observer callback error ({callback.__name__}): {e}")
    
    def set(self, key: str, value: Any, category: str) -> None:
        with self._lock:
            if category not in self._settings:
                self._settings[category] = {}
            self._settings[category][key] = value
        self._save()
        self._notify_observers()

    def reset(self, key: str, category: str) -> None:
        with self._lock:
            if category in self._settings and key in self._settings[category]:
                del self._settings[category][key]
                if not self._settings[category]:
                    del self._settings[category]
        self._save()
        self._notify_observers()

    def get_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._settings)

    def bulk_update(self, updates: dict[str, dict[str, Any]]) -> None:
        with self._lock:
            for category, settings in updates.items():
                if category not in self._settings:
                    self._settings[category] = {}
                self._settings[category].update(settings)
        self._save()
        self._notify_observers()

    def reload(self) -> None:
        self._load()


_runtime_settings: RuntimeSettingsManager | None = None


def get_runtime_settings() -> RuntimeSettingsManager:
    global _runtime_settings
    if _runtime_settings is None:
        _runtime_settings = RuntimeSettingsManager()
    return _runtime_settings
