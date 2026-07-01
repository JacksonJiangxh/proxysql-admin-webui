#!/bin/bash
# Comprehensive API test script

BASE_URL="http://localhost:8080"
USERNAME="admin"
PASSWORD="admin"

# Step 1: Login
echo "=== Login ==="
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

echo "Login response: $LOGIN_RESPONSE"
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null)
echo "✅ Access token obtained: ${ACCESS_TOKEN:0:20}..."

# Step 2: Get CSRF token
echo -e "\n=== Get CSRF Token ==="
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" > /dev/null

CSRF_TOKEN=$(grep "csrf_token" /tmp/cookies.txt | awk '{print $7}')
echo "✅ CSRF token obtained"

# Step 3: Create server config
echo -e "\n=== Create Server Config ==="
SERVER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/servers" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b /tmp/cookies.txt \
  -d '{"name":"Test ProxySQL","host":"127.0.0.1","port":6032,"admin_user":"admin","admin_password":"admin"}')

SERVER_ID=$(echo "$SERVER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "✅ Server config created: $SERVER_ID"

# Step 4: Test table browser
echo -e "\n=== Test Table Browser ==="
TABLE_RESPONSE=$(curl -s "$BASE_URL/api/v1/tables/mysql_servers?server_id=$SERVER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b /tmp/cookies.txt)

echo "$TABLE_RESPONSE" | python3 -m json.tool 2>&1 | head -20

# Step 5: Test dashboard
echo -e "\n=== Test Dashboard ==="
DASHBOARD_RESPONSE=$(curl -s "$BASE_URL/api/v1/dashboard?server_id=$SERVER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b /tmp/cookies.txt)

echo "$DASHBOARD_RESPONSE" | python3 -m json.tool 2>&1 | head -20

echo -e "\n=== All tests completed ==="

# Cleanup
rm -f /tmp/cookies.txt
