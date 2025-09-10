"""
配置管理模块
处理环境变量和配置设置
"""

import os
from typing import Optional, Any
from pathlib import Path


class Config:
    """配置管理类"""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        初始化配置管理
        
        Args:
            env_file: .env文件路径，默认在当前目录查找
        """
        self.env_file = env_file or self._find_env_file()
        self._load_env_file()
    
    def _find_env_file(self) -> Optional[str]:
        """查找.env文件"""
        possible_paths = [
            Path.cwd() / ".env",
            Path(__file__).parent / ".env",
            Path.cwd() / "config" / ".env"
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def _load_env_file(self):
        """加载.env文件"""
        if not self.env_file or not os.path.exists(self.env_file):
            print(f"⚠️  .env文件未找到，将使用默认配置和系统环境变量")
            return
        
        try:
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析键值对
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # 设置环境变量（如果尚未设置）
                        if key not in os.environ:
                            os.environ[key] = value
            
            print(f"✅ 成功加载环境变量文件: {self.env_file}")
            
        except Exception as e:
            print(f"❌ 加载.env文件失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            配置值
        """
        return os.environ.get(key, default)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        获取布尔型配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            布尔值
        """
        value = self.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        获取整数型配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            整数值
        """
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        获取浮点型配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            浮点值
        """
        try:
            return float(self.get(key, default))
        except (ValueError, TypeError):
            return default
    
    @property
    def web3_provider_url(self) -> Optional[str]:
        """Web3提供商URL"""
        return self.get('WEB3_PROVIDER_URL')
    
    @property
    def etherscan_api_key(self) -> Optional[str]:
        """Etherscan API密钥"""
        return self.get('ETHERSCAN_API_KEY')
    
    @property
    def etherscan_base_url(self) -> str:
        """Etherscan API基础URL"""
        return self.get('ETHERSCAN_BASE_URL', 'https://api.etherscan.io/api')
    
    @property
    def target_contract(self) -> Optional[str]:
        """目标合约地址"""
        return self.get('TARGET_CONTRACT')
    
    @property
    def max_workers(self) -> int:
        """最大工作线程数"""
        return self.get_int('MAX_WORKERS', 10)
    
    @property
    def request_delay(self) -> float:
        """请求延迟"""
        return self.get_float('REQUEST_DELAY', 0.2)
    
    @property
    def default_block(self) -> str:
        """默认区块"""
        return self.get('DEFAULT_BLOCK', 'latest')
    
    @property
    def keep_essential_comments(self) -> bool:
        """是否保留重要注释"""
        return self.get_bool('KEEP_ESSENTIAL_COMMENTS', True)
    
    @property
    def output_dir(self) -> str:
        """输出目录"""
        return self.get('OUTPUT_DIR', './analysis_results')
    
    @property
    def log_level(self) -> str:
        """日志级别"""
        return self.get('LOG_LEVEL', 'INFO')
    
    def validate_config(self) -> dict:
        """
        验证配置有效性
        
        Returns:
            验证结果字典
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # 检查必需的配置
        if not self.web3_provider_url:
            results['errors'].append('WEB3_PROVIDER_URL 未设置')
            results['valid'] = False
        elif not self.web3_provider_url.startswith(('http://', 'https://', 'ws://', 'wss://')):
            results['errors'].append('WEB3_PROVIDER_URL 格式无效')
            results['valid'] = False
        
        if not self.etherscan_api_key:
            results['warnings'].append('ETHERSCAN_API_KEY 未设置，将无法获取合约源代码')
        
        # 检查可选配置
        if self.max_workers < 1:
            results['warnings'].append('MAX_WORKERS 应该大于0')
        
        if self.request_delay < 0:
            results['warnings'].append('REQUEST_DELAY 应该大于等于0')
        
        return results
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 当前配置摘要:")
        print(f"   Web3 Provider: {'✅ 已设置' if self.web3_provider_url else '❌ 未设置'}")
        print(f"   Etherscan API: {'✅ 已设置' if self.etherscan_api_key else '❌ 未设置'}")
        print(f"   最大工作线程: {self.max_workers}")
        print(f"   请求延迟: {self.request_delay}s")
        print(f"   默认区块: {self.default_block}")
        print(f"   保留重要注释: {self.keep_essential_comments}")
        print(f"   输出目录: {self.output_dir}")
        print(f"   日志级别: {self.log_level}")


# 全局配置实例
config = Config()


def setup_logging():
    """设置日志"""
    import logging
    
    level_mapping = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR
    }
    
    level = level_mapping.get(config.log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    return logging.getLogger(__name__)


def ensure_output_dir():
    """确保输出目录存在"""
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def load_config_from_env(env_file: Optional[str] = None) -> Config:
    """
    从环境文件加载配置
    
    Args:
        env_file: 环境文件路径
        
    Returns:
        配置实例
    """
    return Config(env_file)


# 使用示例
if __name__ == "__main__":
    # 加载配置
    config = load_config_from_env()
    
    # 打印配置摘要
    config.print_config_summary()
    
    # 验证配置
    validation = config.validate_config()
    
    if validation['valid']:
        print("✅ 配置验证通过")
    else:
        print("❌ 配置验证失败:")
        for error in validation['errors']:
            print(f"   - {error}")
    
    if validation['warnings']:
        print("⚠️  配置警告:")
        for warning in validation['warnings']:
            print(f"   - {warning}")
    
    # 设置日志
    logger = setup_logging()
    logger.info("配置管理模块初始化完成")
