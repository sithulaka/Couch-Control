"""
Configuration loader for Couch Control.
Supports YAML config files with sensible defaults.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# Default configuration
DEFAULT_CONFIG = {
    "server": {
        "port": 8080,
        "host": "0.0.0.0",
    },
    "capture": {
        "quality": 70,
        "fps": 24,
        "scale": 0.75,
        "monitor": 0,
    },
    "security": {
        "pin": "",
        "timeout_minutes": 30,
    },
    "performance": {
        "use_turbojpeg": True,
        "max_clients": 3,
    },
}


def get_config_paths() -> list[Path]:
    """Get list of possible config file locations (in priority order)."""
    paths = []
    
    # 1. Current directory
    paths.append(Path.cwd() / "config.yaml")
    
    # 2. XDG config directory
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg_config:
        paths.append(Path(xdg_config) / "couch-control" / "config.yaml")
    
    # 3. ~/.config/couch-control/
    paths.append(Path.home() / ".config" / "couch-control" / "config.yaml")
    
    # 4. ~/.couch-control.yaml
    paths.append(Path.home() / ".couch-control.yaml")
    
    return paths


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from file.
    
    Args:
        config_path: Explicit config file path. If None, searches default locations.
    
    Returns:
        Configuration dictionary with defaults filled in.
    """
    config = DEFAULT_CONFIG.copy()
    
    # Find config file
    if config_path:
        paths = [config_path]
    else:
        paths = get_config_paths()
    
    # Try each path
    for path in paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    file_config = yaml.safe_load(f) or {}
                config = deep_merge(config, file_config)
                break
            except Exception as e:
                print(f"Warning: Failed to load config from {path}: {e}")
    
    return config


def get_local_ip() -> str:
    """
    Get the local network IP address.
    
    Returns:
        Local IP address string (e.g., "192.168.1.100")
    """
    try:
        import netifaces
        
        # Get all interfaces
        interfaces = netifaces.interfaces()
        
        # Priority order for interface names
        priority = ["eth", "enp", "wlan", "wlp", "eno", "ens"]
        
        for prefix in priority:
            for iface in interfaces:
                if iface.startswith(prefix):
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr.get("addr", "")
                            if ip and not ip.startswith("127."):
                                return ip
        
        # Fallback: try any non-loopback interface
        for iface in interfaces:
            if iface == "lo":
                continue
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get("addr", "")
                    if ip and not ip.startswith("127."):
                        return ip
        
    except ImportError:
        pass
    except Exception:
        pass
    
    # Final fallback
    return "127.0.0.1"


class Config:
    """Configuration wrapper with easy access to settings."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self._config = load_config(config_path)
        
        # Resolve "auto" host
        if self._config["server"]["host"] == "auto":
            self._config["server"]["host"] = get_local_ip()
    
    @property
    def host(self) -> str:
        return self._config["server"]["host"]
    
    @property
    def port(self) -> int:
        return self._config["server"]["port"]
    
    @property
    def quality(self) -> int:
        return self._config["capture"]["quality"]
    
    @property
    def fps(self) -> int:
        return self._config["capture"]["fps"]
    
    @property
    def scale(self) -> float:
        return self._config["capture"]["scale"]
    
    @property
    def monitor(self) -> int:
        return self._config["capture"]["monitor"]
    
    @property
    def pin(self) -> str:
        return self._config["security"]["pin"]
    
    @property
    def timeout_minutes(self) -> int:
        return self._config["security"]["timeout_minutes"]
    
    @property
    def use_turbojpeg(self) -> bool:
        return self._config["performance"]["use_turbojpeg"]
    
    @property
    def max_clients(self) -> int:
        return self._config["performance"]["max_clients"]
    
    @property
    def frame_interval(self) -> float:
        """Get frame interval in seconds based on FPS."""
        return 1.0 / max(1, self.fps)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return config as dictionary."""
        return self._config.copy()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config(config_path: Optional[Path] = None) -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config(config_path)
    return _config
