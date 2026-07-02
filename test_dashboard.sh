#!/bin/bash
# 测试仪表盘模块

echo "=========================================="
echo "测试仪表盘模块"
echo "=========================================="
echo ""

# 步骤1：登录获取token
echo "步骤1：登录获取认证信息..."
login_response=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $(curl -s -X GET http://localhost:8080/api/v1/auth/csrf | jq -r '.csrf_token')" \
  -d '{"username":"admin","password":"admin123"}' \
  -c /tmp/cookies_dash_test.txt)

access_token=$(echo "$login_response" | jq -r '.access_token')

if [ -z "$access_token" ] || [ "$access_token" = "null" ]; then
    echo "❌ 登录失败"
    echo "响应: $login_response"
    exit 1
fi

echo "✅ 登录成功！"
echo ""

# 步骤2：测试仪表盘API
echo "步骤2：测试仪表盘API..."
echo "API: GET /api/v1/dashboard/7384277a/snapshot"
echo ""

dashboard_response=$(curl -s -X GET "http://localhost:8080/api/v1/dashboard/7384277a/snapshot" \
  -H "Authorization: Bearer $access_token" \
  -H "X-CSRF-Token: $(grep csrf_token /tmp/cookies_dash_test.txt | awk '{print $7}')" \
  -b /tmp/cookies_dash_test.txt)

echo "响应："
echo "$dashboard_response" | python3 -m json.tool 2>/dev/null || echo "$dashboard_response"
echo ""

if echo "$dashboard_response" | grep -q '"server_id"'; then
    echo "✅ 仪表盘API测试成功！"
else
    echo "❌ 仪表盘API测试失败"
    echo ""
    echo "详细错误信息："
    echo "$dashboard_response"
fi
echo ""

echo "=========================================="
echo "测试仪表盘模块完成"
echo "=========================================="
