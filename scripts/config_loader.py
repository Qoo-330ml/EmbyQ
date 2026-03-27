# 导入必要的模块
import os      # 用于文件路径和目录操作
import shutil  # 用于文件复制操作
导入yaml# 用于解析和生成YAML配置文件


def get_base_dir():
    """获取项目根目录（EmbyQ目录）
    
    通过获取当前文件的绝对路径，然后向上两级目录，得到项目根目录
    例如：如果当前文件是 scripts/config_loader.py，那么根目录就是 EmbyQ/
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_scripts_dir():
    """获取scripts目录路径
    
    通过获取当前文件的绝对路径，然后向上一级目录，得到scripts目录
    例如：如果当前文件是 scripts/config_loader.py，那么scripts目录就是 scripts/
    """
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    """获取data目录路径
    
    在项目根目录下创建并返回data目录的路径
    例如：如果项目根目录是 EmbyQ/，那么data目录就是 EmbyQ/data/
    """
    return os.path.join(get_base_dir(), 'data')


# 默认配置字典，包含所有可能的配置项及其默认值
DEFAULT_CONFIG = {
    'emby': {
        'server_url': 'https://emby.example.com',  # Emby服务器的URL地址
        'external_url': 'https://emby.example.com',  # Emby服务器的外部访问URL
        'api_key': 'your_api_key_here'  # Emby API密钥
    },
    'service': {
        'external_url': 'https://embyq.example.com:5000'  # EmbyQ服务的外部访问URL
    },
    'database': {
        'name': 'emby_playback.db'  # 数据库文件名
    },
    'monitor': {
        'check_interval': 10  # 监控检查间隔（秒）
    },
    'notifications': {
        'enable_alerts': True,  # 是否启用警报
        'alert_threshold': 2  # 警报阈值
    },
    'security': {
        'auto_disable': True,  # 是否自动禁用违规用户
        'whitelist': ["admin", "user1", "user2"]  # 白名单用户列表
    },
    'webhook': {
        'enabled': False,  # 是否启用webhook通知
        'url': '',  # webhook URL地址
        'timeout': 10,  # webhook请求超时时间（秒）
        'retry_attempts': 3,  # webhook请求失败重试次数
        'title': 'Emby用户封禁通知',  # webhook通知标题
        'content_template': '用户 {username} 在 {location} 使用 {ip_address} ({ip_type}) 登录，检测到 {session_count} 个并发会话，已自动封禁。'  # webhook通知内容模板
    },
    'ip_location': {
        'use_geocache': False  # 是否使用地理位置缓存
    }
}


def load_config():
    """加载配置并管理依赖文件
    
    1. 确保data目录存在
    2. 检查默认配置文件是否存在
    3. 如果用户配置文件不存在，从默认配置文件复制
    4. 加载用户配置
    5. 兼容旧配置格式
    6. 合并默认配置和用户配置
    7. 验证必要配置项
    8. 返回最终配置
    """
    # 获取data目录和scripts目录路径
    data_dir = get_data_dir()
    scripts_dir = get_scripts_dir()
    
    # 确保data目录存在，如果不存在则创建
    os.makedirs(data_dir, exist_ok=True)
    
    # 检查default_config.yaml是否存在
    default_config_path = os.path.join(scripts_dir, 'default_config.yaml')
    if not os.path.exists(default_config_path):
        print("❌ default_config.yaml文件不存在")
        exit(1)  # 如果默认配置文件不存在，退出程序
    
    # 检查data目录下的config.yaml是否存在
    config_file = os.path.join(data_dir, 'config.yaml')
    if not os.path.exists(config_file):
        # 如果不存在，从default_config.yaml复制
        shutil.copy2(default_config_path, config_file)
        print(f"📄 配置文件已生成于: {config_file}，请填写必要项后重启容器")
    
    # 加载用户配置
    with open(config_file, 'r', encoding='utf-8') as f:
        user_config = yaml.safe_load(f) or {}  # 如果文件为空，返回空字典
    
    # 兼容旧配置：emby.check_interval -> monitor.check_interval
    # 处理旧版本配置文件的兼容性
    if user_config.get('emby', {}).get('check_interval') and not user_config.get('monitor', {}).get('check_interval'):
        user_config.setdefault('monitor', {})['check_interval'] = user_config['emby']['check_interval']

    # 深度合并配置：使用默认配置作为基础，用用户配置覆盖
    config = DEFAULT_CONFIG.copy()
    for section in user_config:
        if section in config and isinstance(config[section], dict) and isinstance(user_config[section], dict):
            # 如果是字典类型，更新键值对
            config[section].update(user_config[section])
        否则:
            # 否则直接替换
            config[section] = user_config[section]

    # 确保service配置存在
    if 'service' not in config:
        config['service'] = {'external_url': ''}
    
    # 确保emby.external_url存在，如果不存在则使用server_url
    if 'external_url' not in config.get('emby', {}):
        config['emby']['external_url'] = config['emby'].get('server_url', '')
    
    # 清理旧字段，避免双写
    if 'check_interval' in config.get('emby', {}):
        config['emby'].pop('check_interval', None)
    
    # 验证必要字段
    required_fields = [
        ('emby', 'server_url'),  # Emby服务器URL是必须的
        ('emby', 'api_key')      # Emby API密钥是必须的
    ]
    
    # 检查缺失的必要字段
    missing = []
    对于section, field在required_fields:
        if not config.get(section, {}).get(field):
            missing.append(f"{section}.{field}")
    
    # 如果有缺失的必要字段，打印错误信息并退出
    if missing:
        print("❌ 缺失必要配置项：")
        for item in missing:
            打印(f"  - {项目}")
        退出(1)
    
    # 返回加载好的配置
    return config


def save_config(config):
    """保存配置到文件
    
    将配置字典保存为YAML格式的文件
    
参数：
        config: 要保存的配置字典
    
返回：
        bool: 保存是否成功
    """
    data_dir = get_data_dir()
    config_file = os.path.join(data_dir, 'config.yaml')
    
    try:
        # 以写入模式打开文件，使用utf-8编码
        with open(config_file, 'w', encoding='utf-8') as f:
            # 将配置字典转换为YAML格式并写入文件
            # default_flow_style=False: 使用缩进样式，而不是流式样式
            # allow_unicode=True: 允许unicode字符
            # 缩进=2：缩进为2个空格
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
        return True  # 保存成功
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False  # 保存失败


def get_raw_config():
    """获取原始配置文件内容（用于编辑）
    
    读取并返回配置文件的原始内容，用于Web界面编辑
    
返回：
        str: 配置文件的原始内容，如果文件不存在或读取失败则返回空字符串
    """
    data_dir = get_data_dir()
    config_file = os.path.join(data_dir, 'config.yaml')
    
    if not os.path.exists(config_file):
        return ""  # 如果文件不存在，返回空字符串
    
    try:
        # 以读取模式打开文件，使用utf-8编码
        with open(config_file, 'r', encoding='utf-8') as f:
            return f.read()  # 返回文件内容
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        返回 ""  # 读取失败，返回空字符串
