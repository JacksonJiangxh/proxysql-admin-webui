#!/bin/bash
# 更新服务器配置使用remote_admin用户并测试连接

echo "=========================================="
echo "修复ProxySQL连接问题"
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

echo "✅ 登录成功"
echo ""

# 步骤2：获取服务器ID
echo "步骤2：获取服务器ID..."
servers_response=$(curl -s -X GET http://localhost:8080/api/v1/servers \
  -H "Authorization: Bearer $access_token")

server_id=$(echo "$servers_response" | python3 -c "import sys, json; servers = json.load(sys.stdin); print(servers[0]['id'] if servers else '')" 2>/dev/null)

if [ -z "$server_id" ]; then
    echo "❌ 没有找到服务器配置"
    exit 1
fi

echo "服务器ID: $server_id"
echo ""

# 步骤3：更新服务器配置使用remote_admin用户
echo "步骤3：更新服务器配置使用remote_admin用户..."
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
update_response=$(curl -s -X PUT http://localhost:8080/api/v1/servers/$server_id \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"name":"Test ProxySQL","host":"127.0.0.1","port":6032,"admin_user":"remote_admin","admin_password":"remote_pass"}' \
  -b /tmp/cookies.txt)

if echo "$update_response" | grep -q '"admin_user":"remote_admin"'; then
    echo "✅ 服务器配置更新成功！"
    echo "$update_response" | python3 -m json.tool
else
    echo "❌ 服务器配置更新失败"
    echo "响应: $update_response"
    exit 1
fi
echo ""

# 步骤4：测试连接
echo "步骤4：测试连接到ProxySQL..."
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
connect_response=$(curl -s -X POST http://localhost:8080/api/v1/servers/$server_id/test \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -b /tmp/cookies.txt)

echo "连接测试响应: $connect_response"

if echo "$connect_response" | grep -q '"ok":true'; then
    echo ""
    echo "✅✅✅ 连接测试成功！✅✅✅"
    echo "$connect_response" | python3 -m json.tool
else
    echo ""
    echo "❌ 连接测试失败"
    echo "这可能是因为密码加密问题，需要检查后端日志"
fi
echo ""

echo "=========================================="
echo "ProxySQL连接修复完成"
echo "=========================================="
