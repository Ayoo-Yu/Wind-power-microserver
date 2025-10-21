-- Auth Database Schema
-- Database: windpower_auth

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    department VARCHAR(50),
    position VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User roles association table
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by VARCHAR(50),
    expires_at TIMESTAMP,
    UNIQUE(user_id, role_id)
);

-- Role permissions association table
CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by VARCHAR(50),
    UNIQUE(role_id, permission_id)
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT true
);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'success'
);

-- Farm access permissions
CREATE TABLE IF NOT EXISTS farm_access (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    farm_code VARCHAR(50) NOT NULL,
    access_level VARCHAR(20) NOT NULL DEFAULT 'read', -- read, write, admin
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by VARCHAR(50),
    expires_at TIMESTAMP,
    UNIQUE(user_id, farm_code)
);

-- Password reset tokens
CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Two-factor authentication
CREATE TABLE IF NOT EXISTS two_factor_auth (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    secret_key VARCHAR(255) NOT NULL,
    backup_codes TEXT[],
    is_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_farm_access_user_id ON farm_access(user_id);
CREATE INDEX idx_farm_access_farm_code ON farm_access(farm_code);

-- Insert default roles
INSERT INTO roles (name, description, is_system) VALUES
('admin', 'System Administrator', true),
('operator', 'System Operator', true),
('viewer', 'Read-only User', true),
('manager', 'Farm Manager', true),
('analyst', 'Data Analyst', true);

-- Insert default permissions
INSERT INTO permissions (name, description, resource, action) VALUES
('users.read', 'View user information', 'users', 'read'),
('users.write', 'Create and update users', 'users', 'write'),
('users.delete', 'Delete users', 'users', 'delete'),
('roles.read', 'View roles and permissions', 'roles', 'read'),
('roles.write', 'Create and update roles', 'roles', 'write'),
('data.read', 'View wind farm data', 'data', 'read'),
('data.write', 'Upload and modify data', 'data', 'write'),
('data.delete', 'Delete data', 'data', 'delete'),
('predictions.read', 'View prediction results', 'predictions', 'read'),
('predictions.run', 'Run predictions', 'predictions', 'run'),
('reports.read', 'View reports', 'reports', 'read'),
('reports.generate', 'Generate reports', 'reports', 'generate'),
('simulations.read', 'View simulations', 'simulations', 'read'),
('simulations.run', 'Run simulations', 'simulations', 'run'),
('system.config', 'Configure system settings', 'system', 'config'),
('system.monitor', 'Monitor system status', 'system', 'monitor');

-- Create default admin user (password: admin123)
INSERT INTO users (username, email, password_hash, full_name, is_active, is_verified, created_by) VALUES
('admin', 'admin@windpower.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6', 'System Administrator', true, true, 'system');

-- Assign admin role to admin user
INSERT INTO user_roles (user_id, role_id, assigned_by) VALUES
(1, 1, 'system');

-- Grant all permissions to admin role
INSERT INTO role_permissions (role_id, permission_id, granted_by)
SELECT 1, id, 'system' FROM permissions;