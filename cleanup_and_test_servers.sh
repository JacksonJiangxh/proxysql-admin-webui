#!/bin/bash
# 清理现有服务器并重新测试服务器配置管理模块

echo "=========================================="
echo "清理并重新测试服务器配置管理模块"
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

# 步骤2：删除现有服务器
echo "步骤2：删除现有服务器..."
delete_response=$(curl -s -X DELETE http://localhost:8080/api/v1/servers/9df20798 \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -b /tmp/cookies.txt)

echo "删除响应: $delete_response"
echo ""

# 步骤3：重新测试创建服务器
echo "步骤3：测试创建服务器配置..."
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
create_response=$(curl -s -X POST http://localhost:8080/api/v1/servers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"name":"Test ProxySQL","host":"127.0.0.1","port":6032,"admin_user":"admin","admin_password":"admin"}' \
  -b /tmp/cookies.txt)

server_id=$(echo "$create_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$server_id" ]; then
    echo "❌ 创建服务器配置失败"
    echo "响应: $create_response"
    exit 1
fi

echo "✅ 服务器配置创建成功！"
echo "Server ID: $server_id"
echo ""

# 步骤4：测试更新服务器
echo "步骤4：测试更新服务器配置..."
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
update_response=$(curl -s -X PUT http://localhost:8080/api/v1/servers/$server_id \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -d '{"name":"Test ProxySQL Updated","host":"127.0.0.1","port":6032,"admin_user":"admin","admin_password":"admin"}' \
  -b /tmp/cookies.txt)

if echo "$update_response" | grep -q '"name":"Test ProxySQL Updated"'; then
    echo "✅ 更新服务器配置成功！"
else
    echo "❌ 更新服务器配置失败"
    echo "响应: $update_response"
fi
echo ""

# 步骤5：测试设置默认服务器
echo "步骤5：测试设置默认服务器..."
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
default_response=$(curl -s -X PUT http://localhost:8080/api/v1/servers/$server_id/set-default \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $csrf_token" \
  -b /tmp/cookies.txt)

if echo "$default_response" | grep -q '"is_default":true'; then
    echo "✅ 设置默认服务器成功！"
else
    echo "❌ 设置默认服务器失败"
    echo "响应: $default_response"
fi
echo ""

echo "=========================================="
echo "服务器配置管理模块测试完成（部分）"
echo "=========================================="
echo ""
echo "注意：连接测试可能需要修复ProxySQL ACL配置后才能成功"
