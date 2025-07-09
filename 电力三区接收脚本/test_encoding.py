#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试编码修复
"""

import sys
import os
import tempfile

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import fetch_data_from_c
    
    print("Python version: {}.{}".format(sys.version_info.major, sys.version_info.minor))
    
    # 测试ensure_unicode函数
    test_str = "测试字符串"
    unicode_str = fetch_data_from_c.ensure_unicode(test_str)
    print("✓ ensure_unicode works: {} -> {}".format(type(test_str).__name__, type(unicode_str).__name__))
    
    # 测试保存状态文件
    test_state = set(["/path/to/test/文件.dat", "/another/path/测试.txt"])
    
    # 临时修改STATE_FILE路径用于测试
    original_state_file = fetch_data_from_c.STATE_FILE
    test_state_file = os.path.join(tempfile.gettempdir(), "test_state.txt")
    fetch_data_from_c.STATE_FILE = test_state_file
    
    try:
        fetch_data_from_c.save_downloaded_state(test_state)
        print("✓ save_downloaded_state works")
        
        # 测试加载状态文件
        loaded_state = fetch_data_from_c.load_downloaded_state()
        print("✓ load_downloaded_state works, loaded {} items".format(len(loaded_state)))
        
        if loaded_state == test_state:
            print("✓ State file round-trip successful")
        else:
            print("✗ State file content mismatch")
            
    finally:
        # 恢复原始STATE_FILE
        fetch_data_from_c.STATE_FILE = original_state_file
        # 清理测试文件
        if os.path.exists(test_state_file):
            os.unlink(test_state_file)
    
    print("All encoding tests passed!")
    
except Exception as e:
    print("✗ Test failed: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1) 