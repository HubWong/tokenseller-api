import socket
import random
import logging
from dotenv import dotenv_values, set_key
import requests

logger =logging.getLogger(__name__)

def set_env_if_not_exists(key, value, env_file=".env"):
    config = dotenv_values(env_file)

    if key not in config:
        set_key(env_file, key, value)
        return True

    return False

def check_api_reachable(host: str, timeout: int = 2) -> bool:
    try:
        # 自动补全协议
        url = f"http://{host}" if not host.startswith("http") else host
        
        logger.info(f'one api connecting: {url}')
        # 用 get 也可以，timeout 保证不卡死
        requests.get(f'{url}/health', timeout=timeout, stream=True)
        return True
        
    except:
        return False

def check_port_open(host: str, port: int, timeout: int = 2) -> bool:
    """
    检测指定主机的端口是否开放（TCP）
    :param host: IP 或域名，如 "127.0.0.1" / "baidu.com"
    :param port: 端口号 1~65535
    :param timeout: 超时时间（秒）
    :return: 开放返回 True，关闭/超时返回 False
    """
    try:
        # 创建 socket 对象
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            # 尝试连接
            result = s.connect_ex((host, port))
            # 连接成功返回 0
            return result == 0
    except Exception as ex:
        print('one api connecting:',str(ex))
        return False


def generate_invite_code(length: int = 8) -> str:
    """
    生成随机邀请码（默认：大写字母 + 数字，无易混淆字符）
    :param length: 邀请码长度，默认 8 位
    :return: 随机字符串邀请码
    """
    # 去掉了 0/O/I/l 这些容易混淆的字符
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(chars) for _ in range(length))
