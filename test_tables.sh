#!/bin/bash
# 测试表浏览器模块

echo "=========================================="
echo "测试表浏览器模块"
echo "=========================================="
echo ""

# 步骤1：登录
echo "步骤1：登录..."
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

if [ -z "$access_token" ]; then
    echo "❌ 登录失败"
    exit 1
fi

echo "✅ 登录成功"
echo ""

# 获取服务器ID
servers_response=$(curl -s -X GET http://localhost:8080/api/v1/servers \
  -H "Authorization: Bearer $access_token")

server_id=$(echo "$servers_response" | python3 -c "import sys, json; servers = json.load(sys.stdin); print(servers[0]['id'] if servers else '')" 2>/dev/null)

if [ -z "$server_id" ]; then
    echo "❌ 没有找到服务器配置"
    echo "请先创建服务器配置"
    exit 1
fi

echo "服务器ID: $server_id"
echo ""

# 步骤2：测试列出所有表
echo "步骤2：测试列出所有表..."
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
tables_response=$(curl -s -X GET http://localhost:8080/api/v1/$server_id/tables \
  -H "Authorization: Bearer $access_token")

echo "列出所有表响应: $tables_response" | head -c 500
echo ""

if echo "$tables_response" | grep -q '"table_name"'; then
    echo "✅ 列出所有表成功！"
else
    echo "❌ 列出所有表失败"
    echo "这可能是因为ProxySQL连接问题"
fi
echo ""

echo "=========================================="
echo "表浏览器模块测试完成（部分）"
echo "=========================================="
echo ""
echo "注意：由于ProxySQL连接问题，表浏览器功能可能无法正常工作"
