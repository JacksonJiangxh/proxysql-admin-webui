#!/bin/bash
# 检查现有服务器并清理

echo "检查现有服务器配置..."

# 登录
curl -s -c /tmp/cookies.txt http://localhost:8080/api/v1/users > /dev/null
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')

login_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"username":"admin","password":"admin123"}' \
  -b /tmp/cookies.txt \
  -c /tmp/cookies.txt)

access_token=$(echo "$login_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')

echo "✅ 登录成功"
echo ""

# 获取服务器列表
echo "获取服务器列表..."
servers_response=$(curl -s -X GET http://localhost:8080/api/v1/servers \
  -H "Authorization: Bearer $access_token")

echo "$servers_response" | python3 -m json.tool
