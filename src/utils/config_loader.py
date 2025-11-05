"""
配置加载模块
支持YAML配置文件的加载和管理
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_path: str = "configs/system_config.yaml"):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.load()
        
    def load(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        return self.config
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的路径）
        
        Args:
            key_path: 配置键路径，如 "camera.exposure.default"
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值
        
        Args:
            key_path: 配置键路径
            value: 配置值
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def save(self, output_path: Optional[str] = None):
        """
        保存配置到文件
        
        Args:
            output_path: 输出路径，默认为原配置路径
        """
        save_path = Path(output_path) if output_path else self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        获取配置段
        
        Args:
            section: 段名称
            
        Returns:
            配置段字典
        """
        return self.config.get(section, {})


# 全局配置实例
_config = None


def init_config(config_path: str = "configs/system_config.yaml") -> ConfigLoader:
    """
    初始化全局配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        ConfigLoader实例
    """
    global _config
    _config = ConfigLoader(config_path)
    return _config


def get_config() -> ConfigLoader:
    """
    获取全局配置
    
    Returns:
        ConfigLoader实例
    """
    global _config
    if _config is None:
        _config = ConfigLoader()
    return _config

