#!/bin/bash
# 测试ProxySQL连接

echo "=========================================="
echo "测试ProxySQL连接"
echo "=========================================="
echo ""

# 步骤1：登录获取token和CSRF token
echo "步骤1：登录获取认证信息..."
curl -s -c /tmp/cookies.txt http://localhost:8080/api/v1/users > /dev/null
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')

login_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"username":"admin","password":"admin123"}' \
  -b /tmp/cookies.txt \
  -c /tmp/cookies.txt)

access_token=$(echo "$login_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$access_token" ]; then
    echo "❌ 登录失败"
    exit 1
fi

echo "✅ 登录成功！"
echo ""

# 重新获取CSRF token
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
echo "CSRF token: ${csrf_token:0:20}..."
echo ""

# 步骤2：获取服务器列表
echo "步骤2：获取服务器列表..."
list_response=$(curl -s -X GET http://localhost:8080/api/v1/servers \
  -H "Authorization: Bearer $access_token")

server_id=$(echo "$list_response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0]['id'] if data else '')" 2>/dev/null)

if [ -z "$server_id" ]; then
    echo "❌ 没有找到服务器配置"
    exit 1
fi

echo "✅ 找到服务器配置，ID: $server_id"
echo ""

# 步骤3：测试连接ProxySQL
echo "步骤3：测试连接ProxySQL..."
connection_response=$(curl -s -X POST http://localhost:8080/api/v1/servers/$server_id/test-connection \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -b /tmp/cookies.txt)

echo "连接测试结果："
echo "$connection_response" | python3 -m json.tool

if echo "$connection_response" | grep -q '"success": true'; then
    echo ""
    echo "✅ ProxySQL连接成功！"
else
    echo ""
    echo "❌ ProxySQL连接失败"
fi
echo ""

echo "=========================================="
echo "测试ProxySQL连接完成"
echo "=========================================="
