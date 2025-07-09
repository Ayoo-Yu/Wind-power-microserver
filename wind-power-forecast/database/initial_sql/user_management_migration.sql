-- 检查角色表是否存在，如果不存在则创建
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '{"permissions": []}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 检查用户表是否存在，如果不存在则创建
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    role_id INTEGER REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    first_login BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认角色（如果不存在）
INSERT INTO roles (name, description, permissions)
SELECT '系统管理员', '拥有系统所有权限', '{"permissions": ["manage_users", "train_models", "run_predictions", "view_all_data"]}'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = '系统管理员');

INSERT INTO roles (name, description, permissions)
SELECT '运行操作人员', '可以运行预测和查看数据', '{"permissions": ["run_predictions", "view_all_data"]}'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = '运行操作人员');

INSERT INTO roles (name, description, permissions)
SELECT '普通用户', '只能查看基本数据', '{"permissions": ["view_basic_data"]}'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = '普通用户');

-- 插入默认管理员用户（如果不存在）
-- 密码为 admin123，使用 bcrypt 加密
INSERT INTO users (username, password, full_name, email, role_id, is_active, first_login)
SELECT 'admin', '$2b$10$rR3CQrJ4Ut/Bf6vxiI.YAOGCjmKH7vRm5LWA9O0gWUqCGR6Z/ZnZa', '系统管理员', 'admin@example.com', 
       (SELECT id FROM roles WHERE name = '系统管理员'), TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin'); 