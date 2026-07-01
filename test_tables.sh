#!/bin/bash
# 测试表浏览器模块
BASE_URL="http://localhost:8080/api/v1"
COOKIE_JAR="/tmp/test_cookies.txt"

echo "===== 测试表浏览器模块 ====="
echo

# 清除旧cookie
rm -f "$COOKIE_JAR"

# 1. 登录获取token
echo "1. 登录获取认证token..."
curl -s -c "$COOKIE_JAR" -i -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' > /tmp/login_response.txt

ACCESS_TOKEN=$(grep -o '"access_token":"[^"]*"' /tmp/login_response.txt | head -1 | cut -d'"' -f4)

if [ -z "$ACCESS_TOKEN" ]; then
  echo "错误: 无法获取访问令牌"
  exit 1
fi
echo "  登录成功"
echo

# 2. 获取CSRF token
echo "2. 获取CSRF token..."
curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" -i -X GET "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" > /tmp/csrf_response.txt

XSRF_TOKEN=$(grep 'csrf_token' "$COOKIE_JAR" | awk '{print $7}')
if [ -z "$XSRF_TOKEN" ]; then
  echo "错误: 无法获取CSRF token"
  exit 1
fi
echo "  获取CSRF token成功"
echo

# 3. 获取服务器列表
echo "3. 获取服务器列表..."
SERVERS_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X GET "$BASE_URL/servers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $XSRF_TOKEN")

SERVER_ID=$(echo "$SERVERS_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -z "$SERVER_ID" ]; then
  echo "错误: 无法获取服务器ID"
  echo "响应: $SERVERS_RESPONSE"
  exit 1
fi
echo "  服务器ID: $SERVER_ID"
echo

# 4. 测试列出表（GET /{server_id}/tables）
echo "4. 测试列出表 (GET /$SERVER_ID/tables)..."
TABLES_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X GET "$BASE_URL/$SERVER_ID/tables" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $XSRF_TOKEN")

echo "$TABLES_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TABLES_RESPONSE"
echo

# 检查是否有错误
if echo "$TABLES_RESPONSE" | grep -q "error\|Error\|失败"; then
  echo "警告: 列出表时出现错误"
else
  echo "列出表成功"
fi

echo
echo "===== 测试完成 ====="

# 清理临时文件
rm -f /tmp/login_response.txt /tmp/csrf_response.txt
