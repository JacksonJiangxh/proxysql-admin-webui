#!/bin/bash
# 测试RBAC（基于角色的访问控制）- 修复版（处理CSRF）

echo "Testing RBAC (Role-Based Access Control)..."

# 先获取CSRF token
echo "Step 0: Getting CSRF token..."
curl -s -c /tmp/cookies.txt http://localhost:8080/api/v1/auth/login > /dev/null
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')

if [ -z "$csrf_token" ]; then
    echo "❌ Failed to get CSRF token"
    exit 1
fi

echo "✅ Got CSRF token: ${csrf_token:0:20}..."
echo ""

# 使用CSRF token登录
echo "Step 1: Admin login..."
login_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"username":"admin","password":"admin123"}' \
  -b /tmp/cookies.txt \
  -c /tmp/cookies.txt)

access_token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$access_token" ]; then
    echo "❌ Admin login failed"
    echo "Response: $login_response"
    exit 1
fi

echo "✅ Admin logged in successfully"
echo ""

# 测试1：admin用户访问用户管理API（应该成功）
echo "Test 1: Admin user accessing user management API..."
response1=$(curl -s -X GET http://localhost:8080/api/v1/users \
  -H "Authorization: Bearer $access_token")

if echo "$response1" | grep -q '"username"'; then
    echo "✅ Admin can access user management API"
else
    echo "❌ Admin cannot access user management API"
    echo "Response: $response1"
fi
echo ""

echo "RBAC testing completed (partial)!"
