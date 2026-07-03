#!/bin/bash
# ProxySQL Admin WebUI — API test runner (simplified, JWT-only auth)
#
# Usage:
#   source test_runner.sh
#   api_get  /api/v1/servers
#   api_post /api/v1/servers '{"name":"test","host":"127.0.0.1","port":6032,"admin_user":"proxysql_remote","admin_password":"remote123"}'
#   api_put  /api/v1/servers/ID '{"name":"updated"}'
#   api_delete /api/v1/servers/ID

BASE_URL="http://127.0.0.1:8080"
ADMIN_USER="admin"
ADMIN_PASS="admin123"
SERVER_ID=""  # Will be set after login+server lookup

# ── helpers ──────────────────────────────────────────────────
_json() {
    python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || cat
}

_login() {
    local resp
    resp=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
    TOKEN=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
    export TOKEN
}

_refresh_auth() {
    if [ -z "$TOKEN" ] || ! curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "$BASE_URL/api/v1/health" | grep -q "200"; then
        _login
    fi
}

# ── API methods ──────────────────────────────────────────────
api_get() {
    local path="$1"
    _refresh_auth
    curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL$path" | _json
}

api_post() {
    local path="$1" data="$2"
    _refresh_auth
    curl -s -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$data" "$BASE_URL$path" | _json
}

api_put() {
    local path="$1" data="$2"
    _refresh_auth
    curl -s -X PUT \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$data" "$BASE_URL$path" | _json
}

api_delete() {
    local path="$1"
    _refresh_auth
    curl -s -X DELETE \
        -H "Authorization: Bearer $TOKEN" \
        "$BASE_URL$path" | _json
}

# ── init ─────────────────────────────────────────────────────
_init() {
    _login
    # Get the first server ID
    SERVER_ID=$(api_get "/api/v1/servers" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
    export SERVER_ID
    echo "Initialized. SERVER_ID=$SERVER_ID"
}

# Auto-init if sourced
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
    _init
fi
