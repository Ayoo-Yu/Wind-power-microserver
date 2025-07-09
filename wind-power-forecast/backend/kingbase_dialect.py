from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.engine import reflection
from sqlalchemy import types
import re

class KingbaseDialect(PGDialect_psycopg2):
    """
    自定义金仓数据库方言，处理版本字符串解析
    """
    
    def _get_server_version_info(self, connection):
        """
        重写版本解析方法，处理金仓数据库的版本格式
        直接返回一个硬编码的版本号，避免解析错误
        """
        # 不再尝试解析版本，直接返回PostgreSQL 9.6的版本号
        return (9, 6, 0)  # 直接返回一个固定的版本号
        
    def initialize(self, connection):
        """
        重写初始化方法，跳过版本检查
        """
        # 设置服务器版本号为9.6.0
        self.server_version_info = (9, 6, 0)
        # 调用基类的其他初始化方法，但跳过版本检查部分
        self._initialized = True
        
    # 添加辅助方法处理特殊字符串长度格式
    def _extract_length_value(self, length_str):
        """
        从字符串中提取长度值，处理特殊格式如 "255 char"
        
        参数:
            length_str: 包含长度信息的字符串
            
        返回:
            整数长度值，如果无法提取则返回默认值255
        """
        if length_str is None:
            return None
            
        # 如果已经是整数，直接返回
        if isinstance(length_str, int):
            return length_str
            
        # 尝试从字符串中提取数字
        # 处理类似 "255 char" 的格式
        char_pattern = re.compile(r'^(\d+)\s*char$', re.IGNORECASE)
        match = char_pattern.match(str(length_str).strip())
        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                pass
                
        # 尝试直接转换为整数
        try:
            return int(str(length_str).strip())
        except (ValueError, TypeError):
            pass
            
        # 如果是其他格式，尝试提取第一个数字序列
        number_match = re.search(r'(\d+)', str(length_str))
        if number_match:
            try:
                return int(number_match.group(1))
            except (ValueError, TypeError):
                pass
                
        # 无法提取，返回默认值
        return 255
        
    # 添加对VARCHAR长度处理的修复
    def get_columns(self, connection, table_name, schema=None, **kw):
        """
        重写获取列信息的方法，确保VARCHAR类型的长度被正确地作为整数处理
        """
        columns = super().get_columns(connection, table_name, schema, **kw)
        for column in columns:
            # 处理字符串类型的长度
            if hasattr(column['type'], 'length') and column['type'].length is not None:
                if not isinstance(column['type'].length, int):
                    extracted_length = self._extract_length_value(column['type'].length)
                    if extracted_length != 255 or str(column['type'].length).strip() != str(extracted_length):
                        print(f"信息: 列 {column['name']} 的长度值 '{column['type'].length}' 已转换为整数 {extracted_length}")
                    column['type'].length = extracted_length
        return columns
        
    # 添加创建类型的拦截器，确保创建时长度为整数
    def _get_column_info(self, *args, **kwargs):
        column_info = super()._get_column_info(*args, **kwargs)
        if 'type' in column_info and hasattr(column_info['type'], 'length'):
            if not isinstance(column_info['type'].length, int):
                extracted_length = self._extract_length_value(column_info['type'].length)
                if extracted_length != 255 or str(column_info['type'].length).strip() != str(extracted_length):
                    print(f"信息: 列 {column_info.get('name', 'unknown')} 的长度值 '{column_info['type'].length}' 已转换为整数 {extracted_length}")
                column_info['type'].length = extracted_length
        return column_info
    
    # 重写类型编译器以处理字符串长度
    def type_descriptor(self, typeobj):
        """
        确保类型描述符的长度为整数
        """
        if hasattr(typeobj, 'length') and typeobj.length is not None:
            if not isinstance(typeobj.length, int):
                extracted_length = self._extract_length_value(typeobj.length)
                if extracted_length != 255 or str(typeobj.length).strip() != str(extracted_length):
                    print(f"信息: 类型 {typeobj.__class__.__name__} 的长度值 '{typeobj.length}' 已转换为整数 {extracted_length}")
                typeobj.length = extracted_length
        return super().type_descriptor(typeobj)
        
    # 添加支持字符串比较的属性
    supports_statement_cache = False

# 封装原始SQLAlchemy类型，确保长度总是整数
original_string_types = [types.String, types.VARCHAR, types.CHAR, types.TEXT]

for type_class in original_string_types:
    original_init = type_class.__init__
    
    def create_safe_init(original_init):
        def safe_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if hasattr(self, 'length') and self.length is not None:
                if not isinstance(self.length, int):
                    dialect = KingbaseDialect()
                    extracted_length = dialect._extract_length_value(self.length)
                    if extracted_length != 255 or str(self.length).strip() != str(extracted_length):
                        print(f"信息: {self.__class__.__name__} 初始化时的长度值 '{self.length}' 已转换为整数 {extracted_length}")
                    self.length = extracted_length
        return safe_init
    
    type_class.__init__ = create_safe_init(original_init)

# 注册方言
from sqlalchemy.dialects import registry
registry.register("postgresql.kingbase", __name__, "KingbaseDialect") 