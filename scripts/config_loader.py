import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


@lru_cache(maxsize=None)
def get_base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def get_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def get_data_dir() -> Path:
    return get_base_dir() / 'data'


DEFAULT_CONFIG: Dict[str, Any] = {
    'emby': {
        'server_url': 'https://emby.example.com',
        'external_url': 'https://emby.example.com',
        'api_key': 'your_api_key_here',
    },
    'service': {
        'external_url': 'https://embyq.example.com:5000',
    },
    'database': {
        'name': 'emby_playback.db',
    },
    'monitor': {
        'check_interval': 10,
    },
    'notifications': {
        'enable_alerts': True,
        'alert_threshold': 2,
    },
    'security': {
        'auto_disable': True,
        'whitelist': ['admin', 'user1', 'user2'],
    },
    'webhook': {
        'enabled': False,
        'url': '',
        'timeout': 10,
        'retry_attempts': 3,
        'title': 'Emby用户封禁通知',
        'content_template': '用户 {username} 在 {location} 使用 {ip_address} ({ip_type}) 登录，检测到 {session_count} 个并发会话，已自动封禁。',
    },
    'ip_location': {
        'use_geocache': False,
    },
}


def load_config() -> Tuple[Dict[str, Any], list]:
    data_dir = get_data_dir()
    scripts_dir = get_scripts_dir()
    
    data_dir.mkdir(parents=True, exist_ok=True)
    
    default_config_path = scripts_dir / 'default_config.yaml'
    if not default_config_path.exists():
        print("❌ default_config.yaml文件不存在")
        raise SystemExit(1)
    
    user_config_path = data_dir / 'config.yaml'
    if not user_config_path.exists():
        shutil.copy2(default_config_path, user_config_path)
        print(f"📄 配置文件已生成于: {user_config_path}")
    
    with open(user_config_path, 'r', encoding='utf-8') as f:
        user_config = yaml.safe_load(f) or {}
    
    config = _merge_config(DEFAULT_CONFIG, user_config)
    missing = _validate_required_fields(config)
    
    return config, missing


def save_config(config: Dict[str, Any]) -> bool:
    config_path = get_data_dir() / 'config.yaml'
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2, sort_keys=False)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False


def get_raw_config() -> str:
    config_path = get_data_dir() / 'config.yaml'
    
    if not config_path.exists():
        return ""
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return ""


def is_config_valid(config: Dict[str, Any]) -> bool:
    return len(_validate_required_fields(config)) == 0


def _merge_config(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    result = default.copy()
    
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    
    return result


def _validate_required_fields(config: Dict[str, Any]) -> list:
    required_fields = [
        ('emby', 'server_url'),
        ('emby', 'api_key'),
    ]
    
    missing = []
    for section, field in required_fields:
        value = config.get(section, {}).get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(f"{section}.{field}")
    
    return missing
