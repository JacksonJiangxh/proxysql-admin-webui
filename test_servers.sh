#!/bin/bash
# 测试服务器配置管理模块
BASE_URL="http://localhost:8080/api/v1"
COOKIE_JAR="/tmp/test_cookies.txt"

echo "===== 测试服务器配置管理模块 ====="
echo

# 清除旧cookie
rm -f "$COOKIE_JAR"

# 1. 登录获取token
echo "1. 登录获取认证token..."
curl -s -c "$COOKIE_JAR" -i -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' > /tmp/login_response.txt

ACCESS_TOKEN=$(grep -o '"access_token":"[^"]*"' /tmp/login_response.txt | head -1 | cut -d'"' -f4)

echo "  访问令牌获取: ${ACCESS_TOKEN:+成功}${ACCESS_TOKEN:-失败}"
echo

if [ -z "$ACCESS_TOKEN" ]; then
  echo "错误: 无法获取访问令牌，请检查认证服务"
  cat /tmp/login_response.txt
  exit 1
fi

# 2. 获取CSRF token（通过发送GET请求，服务器会设置csrf_token cookie）
echo "2. 获取CSRF token（发送GET请求）..."
curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" -i -X GET "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" > /tmp/csrf_response.txt

# 从cookie jar中提取csrf_token
XSRF_TOKEN=$(grep 'csrf_token' "$COOKIE_JAR" | awk '{print $7}')

echo "  CSRF令牌获取: ${XSRF_TOKEN:+成功}${XSRF_TOKEN:-失败}"
echo "  CSRF Token (前20字符): ${XSRF_TOKEN:0:20}..."
echo

if [ -z "$XSRF_TOKEN" ]; then
  echo "错误: 无法获取CSRF token"
  echo "Cookie jar内容:"
  cat "$COOKIE_JAR"
  exit 1
fi

# 3. 列出所有服务器配置
echo "3. 测试列出服务器配置 (GET /servers)..."
LIST_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X GET "$BASE_URL/servers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $XSRF_TOKEN")

echo "$LIST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LIST_RESPONSE"
echo

# 4. 创建新服务器配置
echo "4. 测试创建服务器配置 (POST /servers)..."
CREATE_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X POST "$BASE_URL/servers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $XSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-proxysql-'$(date +%s)'",
    "host": "127.0.0.1",
    "port": 6032,
    "admin_user": "admin",
    "admin_password": "admin",
    "is_default": false,
    "hide_tables": ""
  }')

echo "$CREATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CREATE_RESPONSE"
echo

# 提取服务器ID
SERVER_ID=$(echo "$CREATE_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$SERVER_ID" ]; then
  echo "警告: 无法创建服务器配置"
  echo "尝试获取现有服务器列表..."
  SERVER_ID=$(echo "$LIST_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
  echo "使用现有服务器ID: $SERVER_ID"
fi

# 5. 获取服务器详情
if [ -n "$SERVER_ID" ]; then
  echo "5. 测试获取服务器详情 (GET /servers/$SERVER_ID)..."
  GET_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X GET "$BASE_URL/servers/$SERVER_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-CSRF-Token: $XSRF_TOKEN")
  
  echo "$GET_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$GET_RESPONSE"
  echo

  # 6. 更新服务器配置
  echo "6. 测试更新服务器配置 (PUT /servers/$SERVER_ID)..."
  UPDATE_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X PUT "$BASE_URL/servers/$SERVER_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-CSRF-Token: $XSRF_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "test-proxysql-updated",
      "hide_tables": "sqlite_stat1,sqlite_stat4"
    }')
  
  echo "$UPDATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$UPDATE_RESPONSE"
  echo

  # 7. 测试连接
  echo "7. 测试连接测试端点 (POST /servers/$SERVER_ID/test)..."
  TEST_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X POST "$BASE_URL/servers/$SERVER_ID/test" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-CSRF-Token: $XSRF_TOKEN")
  
  echo "$TEST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TEST_RESPONSE"
  echo

  # 8. 删除服务器配置
  echo "8. 测试删除服务器配置 (DELETE /servers/$SERVER_ID)..."
  DELETE_RESPONSE=$(curl -s -b "$COOKIE_JAR" -X DELETE "$BASE_URL/servers/$SERVER_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "X-CSRF-Token: $XSRF_TOKEN")
  
  echo "$DELETE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DELETE_RESPONSE"
  echo
else
  echo "跳过详细测试（无服务器ID）"
fi

echo "===== 测试完成 ====="

# 清理临时文件
rm -f /tmp/login_response.txt /tmp/csrf_response.txt
