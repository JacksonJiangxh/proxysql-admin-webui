#!/bin/bash
# 完整的认证模块测试脚本

echo "=========================================="
echo "完整认证模块测试"
echo "=========================================="
echo ""

# 步骤1：获取CSRF token
echo "步骤1：获取CSRF token..."
curl -s -c /tmp/cookies.txt http://localhost:8080/api/v1/users > /dev/null
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')

if [ -z "$csrf_token" ]; then
    echo "❌ 无法获取CSRF token"
    exit 1
fi

echo "✅ 获取到CSRF token: ${csrf_token:0:20}..."
echo ""

# 步骤2：测试登录功能
echo "步骤2：测试登录功能..."
login_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"username":"admin","password":"admin123"}' \
  -b /tmp/cookies.txt \
  -c /tmp/cookies.txt)

access_token=$(echo "$login_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$access_token" ]; then
    echo "❌ 登录失败"
    echo "响应: $login_response"
    exit 1
fi

echo "✅ 登录成功！"
echo "Access token: ${access_token:0:50}..."
echo ""

# 步骤3：测试Token刷新功能
echo "步骤3：测试Token刷新功能..."
refresh_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/refresh \
  -H "X-CSRF-Token: $csrf_token" \
  -b /tmp/cookies.txt)

new_token=$(echo "$refresh_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$new_token" ]; then
    echo "❌ Token刷新失败"
    echo "响应: $refresh_response"
else
    echo "✅ Token刷新成功！"
    echo "New access token: ${new_token:0:50}..."
fi
echo ""

# 步骤4：测试RBAC（创建viewer用户）
echo "步骤4：测试RBAC（创建viewer用户）..."

# 重新获取CSRF token（可能已经旋转）
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')

create_response=$(curl -s -X POST http://localhost:8080/api/v1/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"username":"viewer1","password":"test123","role":"viewer","email":"viewer1@test.com"}' \
  -b /tmp/cookies.txt)

if echo "$create_response" | grep -q '"username":"viewer1"'; then
    echo "✅ Viewer用户创建成功！"
else
    echo "❌ Viewer用户创建失败"
    echo "响应: $create_response"
fi
echo ""

echo "=========================================="
echo "认证模块测试完成！"
echo "=========================================="
