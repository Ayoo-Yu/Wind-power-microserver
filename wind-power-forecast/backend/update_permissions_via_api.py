#!/usr/bin/env python3
"""
通过现有API更新角色权限的简单脚本
"""
import requests
import json

# API基础URL
BASE_URL = "http://localhost:5000/api"

# 新的权限配置
ROLE_PERMISSIONS = {
    "系统管理员": {
        "permissions": [
            # 用户管理权限
            "manage_users",
            "manage_roles",
            # 数据访问权限
            "view_all_data",
            "upload_files",
            "download_files",
            # 模型和预测权限
            "train_models",
            "run_predictions",
            "run_simulations",
            # 系统管理权限
            "configure_system",
            "system_maintenance",
            "manage_reports",
            "manage_weather_data",
            # 基础权限
            "view_dashboard",
            "manage_tasks"
        ]
    },
    "运行操作人员": {
        "permissions": [
            # 数据访问权限
            "view_all_data",
            "upload_files",
            "download_files",
            # 模型和预测权限
            "train_models",
            "run_predictions",
            "run_simulations",
            # 系统管理权限（除了用户管理和系统维护）
            "configure_system",
            "manage_reports",
            "manage_weather_data",
            # 基础权限
            "view_dashboard",
            "manage_tasks"
        ]
    },
    "普通人员": {
        "permissions": [
            # 数据访问权限
            "view_all_data",
            # 模型和预测权限
            "train_models",
            "run_predictions",
            "run_simulations",
            # 基础权限
            "view_dashboard"
        ]
    }
}

def get_all_roles():
    """获取所有角色"""
    try:
        response = requests.get(f"{BASE_URL}/roles")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取角色失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def update_role_permissions(role_id, role_name, permissions):
    """更新角色权限"""
    try:
        data = {
            "permissions": permissions
        }
        response = requests.put(f"{BASE_URL}/roles/{role_id}", json=data)
        if response.status_code == 200:
            print(f"✅ 成功更新角色 '{role_name}' 的权限")
            return True
        else:
            print(f"❌ 更新角色 '{role_name}' 失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def main():
    """主函数"""
    print("🔄 开始更新角色权限...")
    
    # 获取所有角色
    roles = get_all_roles()
    if not roles:
        print("❌ 无法获取角色列表，请检查API服务是否正常运行")
        return
    
    print(f"📋 找到 {len(roles)} 个角色")
    
    # 更新每个角色的权限
    updated_count = 0
    for role in roles:
        role_name = role['name']
        role_id = role['id']
        
        if role_name in ROLE_PERMISSIONS:
            print(f"🔧 正在更新角色: {role_name}")
            if update_role_permissions(role_id, role_name, ROLE_PERMISSIONS[role_name]):
                updated_count += 1
        else:
            print(f"⚠️ 跳过未知角色: {role_name}")
    
    print(f"\n🎉 权限更新完成！共更新了 {updated_count} 个角色")
    
    # 验证更新结果
    print("\n📊 验证更新结果:")
    updated_roles = get_all_roles()
    if updated_roles:
        for role in updated_roles:
            if role['name'] in ROLE_PERMISSIONS:
                print(f"  - {role['name']}: {len(role['permissions'].get('permissions', []))} 个权限")

if __name__ == "__main__":
    main() 