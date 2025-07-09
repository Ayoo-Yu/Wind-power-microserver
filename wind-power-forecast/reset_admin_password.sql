-- 使用一个简单直接的密码哈希
-- 这是'admin123'使用的哈希值
UPDATE users 
SET password_hash = 'pbkdf2:sha256:150000$fLahYBPZ$87a70c634e3a6243e25bc92a69f46a83a92d12a4b51156c7a0cd76bb9ac5a9a8' 
WHERE username = 'admin'; 