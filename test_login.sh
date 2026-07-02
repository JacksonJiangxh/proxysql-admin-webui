#!/bin/bash
# 测试登录API

echo "Testing login API..."
response=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

echo "Response: $response"

# 检查是否包含access_token
if echo "$response" | grep -q "access_token"; then
    echo "✅ Login successful!"
    echo "$response" | python3 -m json.tool
else
    echo "❌ Login failed!"
    echo "$response"
fi
