#!/bin/bash
# 测试服务器配置管理模块

echo "=========================================="
echo "测试服务器配置管理模块"
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

# 重新获取CSRF token（登录后可能已经旋转）
csrf_token=$(grep 'csrf_token' /tmp/cookies.txt | awk '{print $7}')
echo "CSRF token: ${csrf_token:0:20}..."
echo ""

# 步骤2：测试创建服务器配置
echo "步骤2：测试创建服务器配置..."
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
else
    echo "✅ 服务器配置创建成功！"
    echo "Server ID: $server_id"
fi
echo ""

# 步骤3：测试获取服务器列表
echo "步骤3：测试获取服务器列表..."
list_response=$(curl -s -X GET http://localhost:8080/api/v1/servers \
  -H "Authorization: Bearer $access_token")

if echo "$list_response" | grep -q '"name"'; then
    echo "✅ 获取服务器列表成功！"
    echo "$list_response" | python3 -m json.tool | head -20
else
    echo "❌ 获取服务器列表失败"
    echo "响应: $list_response"
fi
echo ""

# 步骤4：测试获取服务器详情
if [ ! -z "$server_id" ]; then
    echo "步骤4：测试获取服务器详情..."
    detail_response=$(curl -s -X GET http://localhost:8080/api/v1/servers/$server_id \
      -H "Authorization: Bearer $access_token")
    
    if echo "$detail_response" | grep -q '"name"'; then
        echo "✅ 获取服务器详情成功！"
        echo "$detail_response" | python3 -m json.tool
    else
        echo "❌ 获取服务器详情失败"
        echo "响应: $detail_response"
    fi
    echo ""
fi

echo "=========================================="
echo "服务器配置管理模块测试完成（部分）"
echo "=========================================="
