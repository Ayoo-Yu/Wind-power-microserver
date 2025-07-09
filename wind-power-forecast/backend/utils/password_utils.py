"""
密码工具模块 - 提供统一的密码哈希和验证功能
"""
from werkzeug.security import generate_password_hash as werkzeug_generate_hash
from werkzeug.security import check_password_hash

# 统一的哈希方法和参数
HASH_METHOD = 'pbkdf2:sha256'
SALT_LENGTH = 16
ITERATIONS = 150000  # 固定迭代次数，避免版本差异

def generate_password_hash(password):
    """
    使用统一参数生成密码哈希
    """
    return werkzeug_generate_hash(
        password, 
        method=HASH_METHOD,
        salt_length=SALT_LENGTH
    )

def verify_password(password, password_hash):
    """
    验证密码哈希
    """
    # 如果哈希值前缀不匹配我们的标准格式，提供更多详细日志
    if not password_hash.startswith(f"{HASH_METHOD}:"):
        print(f"警告: 哈希格式不一致，预期 '{HASH_METHOD}:'，实际 '{password_hash[:15]}...'")
        
    return check_password_hash(password_hash, password)

def get_debug_hash(password="admin123"):
    """
    生成调试用的标准哈希，用于故障排除
    """
    hash_value = generate_password_hash(password)
    return f"使用 '{password}' 生成的标准哈希: {hash_value}" 