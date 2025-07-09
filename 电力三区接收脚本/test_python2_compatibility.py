#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Python 2兼容性测试脚本
"""

import sys

def test_syntax():
    """测试语法兼容性"""
    try:
        # 测试导入主要模块
        print("Testing import of fetch_data_from_c...")
        import fetch_data_from_c
        print("✓ fetch_data_from_c imported successfully")
        
        print("Testing import of cleanup_state...")
        import cleanup_state
        print("✓ cleanup_state imported successfully")
        
        # 测试基本函数
        print("Testing makedirs_exist_ok function...")
        fetch_data_from_c.makedirs_exist_ok("/tmp/test_dir")
        print("✓ makedirs_exist_ok works")
        
        print("All tests passed! Scripts are Python 2 compatible.")
        return True
        
    except SyntaxError as e:
        print("✗ Syntax Error: {}".format(e))
        return False
    except ImportError as e:
        print("✗ Import Error: {}".format(e))
        return False
    except Exception as e:
        print("✗ Other Error: {}".format(e))
        return False

if __name__ == "__main__":
    print("Python version: {}.{}".format(sys.version_info.major, sys.version_info.minor))
    
    if test_syntax():
        sys.exit(0)
    else:
        sys.exit(1) 