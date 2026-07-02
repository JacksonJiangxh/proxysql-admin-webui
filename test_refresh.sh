#!/bin/bash
# 测试JWT token刷新功能（正确版本）

echo "Testing token refresh API..."

# 先登录获取token（refresh_token在cookie中）
login_response=$(curl -s -i -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  -c /tmp/cookies.txt)

# 提取access_token
access_token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$access_token" ]; then
    echo "❌ Failed to get access_token from login response"
    echo "Login response: $login_response"
    exit 1
fi

echo "✅ Login successful!"
echo "Access token: ${access_token:0:50}..."

# 使用cookie中的refresh_token获取新的access_token
refresh_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -b /tmp/cookies.txt)

echo "Refresh response: $refresh_response"

# 检查是否包含新的access_token
if echo "$refresh_response" | grep -q "access_token"; then
    echo "✅ Token refresh successful!"
    echo "$refresh_response" | python3 -m json.tool
else
    echo "❌ Token refresh failed!"
fi
