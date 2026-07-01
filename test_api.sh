#!/bin/bash
# Test script for API endpoints with CSRF handling

BASE_URL="http://localhost:8080"
USERNAME="admin"
PASSWORD="admin"

# Step 1: Login to get JWT token
echo "=== Step 1: Login ==="
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
echo "Access token obtained: ${ACCESS_TOKEN:0:50}..."

# Step 2: Get CSRF token by making a GET request
echo -e "\n=== Step 2: Get CSRF Token ==="
GET_RESPONSE=$(curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt \
  "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "Response: $GET_RESPONSE"

# Extract CSRF token from cookie
CSRF_TOKEN=$(grep "csrf_token" /tmp/cookies.txt | awk '{print $7}')
echo "CSRF token from cookie: $CSRF_TOKEN"

# Step 3: Test POST request with CSRF token
echo -e "\n=== Step 3: Test POST Request ==="
POST_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/servers" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b /tmp/cookies.txt \
  -d '{"name":"Test ProxySQL","host":"127.0.0.1","port":6032,"admin_user":"admin","admin_password":"admin","description":"Test server"}')

echo "POST response: $POST_RESPONSE"

# Cleanup
rm -f /tmp/cookies.txt
