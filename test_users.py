#!/usr/bin/env python3
"""测试用户管理模块"""
import json
import http.cookiejar
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080/api/v1"
COOKIE_JAR = "/tmp/test_cookies.txt"

# 创建cookie jar
cookie_jar_obj = http.cookiejar.MozillaCookieJar(COOKIE_JAR)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar_obj))

# 1. 登录
print("1. 登录获取认证token...")
data = json.dumps({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request(f'{BASE_URL}/auth/login', data=data, headers={'Content-Type': 'application/json'})
try:
    resp = opener.open(req)
    token_data = json.loads(resp.read())
    access_token = token_data['access_token']
    print(f'  登录成功')
except Exception as e:
    print(f'  登录失败: {e}')
    exit(1)

# 2. 获取CSRF token
print("2. 获取CSRF token...")
req = urllib.request.Request(f'{BASE_URL}/auth/me', headers={'Authorization': f'Bearer {access_token}'})
try:
    resp = opener.open(req)
    print('  获取CSRF token成功')
except Exception as e:
    print(f'  获取CSRF token失败: {e}')
    exit(1)

# 读取CSRF token from cookie
csrf_token = None
for cookie in cookie_jar_obj:
    if cookie.name == 'csrf_token':
        csrf_token = cookie.value
        break
print(f'  CSRF token: {csrf_token[:20]}...' if csrf_token else '  未找到CSRF token')

# 3. 测试用户管理模块
print("3. 测试列出用户 (GET /users)...")
req = urllib.request.Request(f'{BASE_URL}/users', headers={
    'Authorization': f'Bearer {access_token}',
    'X-CSRF-Token': csrf_token,
})
try:
    resp = opener.open(req)
    users_data = json.loads(resp.read())
    print(f'  成功，返回 {len(users_data)} 个用户')
    print(f'  第一个用户: {json.dumps(users_data[0], indent=2)[:100]}...')
except urllib.error.HTTPError as e:
    print(f'  失败: {e.code} {e.reason}')
    print(f'  响应: {e.read().decode()}')
except Exception as e:
    print(f'  失败: {e}')

print("\n===== 测试完成 =====")
