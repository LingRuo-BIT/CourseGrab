# -*- coding: utf-8 -*-
"""
mitmproxy 代理脚本
用于捕获 BIT 选课系统的认证 Cookie

使用方法：
1. 安装 mitmproxy: pip install mitmproxy
2. 运行: mitmdump -s proxy_addon.py -p 8888
3. 配置浏览器代理指向 localhost:8888
4. 访问 BIT 选课系统并登录
5. Cookie 自动保存到数据库
"""

import json
import time
import asyncio
import threading
from mitmproxy import http, ctx
from urllib.parse import urlparse
import sqlite3
import os

# 目标域名
TARGET_DOMAINS = [
    "xk.bit.edu.cn",
    "yjsxkapp.bit.edu.cn", 
    "login.bit.edu.cn",
    "jxzx.bit.edu.cn"
]

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "coursegrab.db")


class CookieCaptureAddon:
    """Cookie 捕获插件"""
    
    def __init__(self):
        self.cookies = {}
        self.csrf_token = None
        self.last_capture_time = None
        
    def request(self, flow: http.HTTPFlow) -> None:
        """处理请求，提取 Cookie"""
        host = flow.request.host
        
        # 检查是否是目标域名
        if not any(domain in host for domain in TARGET_DOMAINS):
            return
        
        # 提取请求中的 Cookie
        cookie_header = flow.request.headers.get("Cookie", "")
        if cookie_header:
            self._parse_cookies(cookie_header)
            
        # 检查是否有 csrfToken 参数
        if flow.request.method == "POST":
            content = flow.request.get_text()
            if "csrfToken=" in content:
                # 提取 csrfToken
                for pair in content.split("&"):
                    if pair.startswith("csrfToken="):
                        self.csrf_token = pair.split("=")[1]
                        ctx.log.info(f"[CookieCapture] 捕获 csrfToken: {self.csrf_token[:20]}...")
                        break
    
    def response(self, flow: http.HTTPFlow) -> None:
        """处理响应，提取 Set-Cookie"""
        host = flow.request.host
        
        if not any(domain in host for domain in TARGET_DOMAINS):
            return
        
        # 提取 Set-Cookie 头
        for key, value in flow.response.headers.items(multi=True):
            if key.lower() == "set-cookie":
                self._parse_set_cookie(value)
        
        # 检查响应中的 csrfToken
        if flow.response.headers.get("content-type", "").startswith("application/json"):
            try:
                data = json.loads(flow.response.get_text())
                if isinstance(data, dict) and "csrfToken" in data:
                    self.csrf_token = data["csrfToken"]
                    ctx.log.info(f"[CookieCapture] 从响应捕获 csrfToken")
            except:
                pass
        
        # 如果收集到足够的 Cookie，保存到数据库
        if self._has_valid_cookies():
            self._save_to_database()
    
    def _parse_cookies(self, cookie_str: str):
        """解析 Cookie 字符串"""
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                self.cookies[key.strip()] = value.strip()
    
    def _parse_set_cookie(self, set_cookie: str):
        """解析 Set-Cookie 头"""
        parts = set_cookie.split(";")
        if parts:
            first_part = parts[0].strip()
            if "=" in first_part:
                key, value = first_part.split("=", 1)
                self.cookies[key.strip()] = value.strip()
                ctx.log.info(f"[CookieCapture] 捕获 Cookie: {key}")
    
    def _has_valid_cookies(self) -> bool:
        """检查是否有有效的认证 Cookie"""
        # 检查关键 Cookie 是否存在
        key_cookies = ["JSESSIONID", "MOD_AUTH_CAS", "CASTGC"]
        found = sum(1 for k in key_cookies if k in self.cookies)
        return found >= 1  # 至少有一个关键 Cookie
    
    def _save_to_database(self):
        """保存 Cookie 到数据库"""
        # 防止频繁保存
        if self.last_capture_time and time.time() - self.last_capture_time < 5:
            return
        
        self.last_capture_time = time.time()
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 创建表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cookies TEXT,
                    csrf_token TEXT,
                    is_valid INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cookies_json = json.dumps(self.cookies)
            
            # 检查是否已有记录
            cursor.execute("SELECT id FROM credentials LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                # 更新现有记录
                cursor.execute('''
                    UPDATE credentials 
                    SET cookies = ?, csrf_token = ?, is_valid = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (cookies_json, self.csrf_token, row[0]))
            else:
                # 插入新记录
                cursor.execute('''
                    INSERT INTO credentials (cookies, csrf_token, is_valid)
                    VALUES (?, ?, 1)
                ''', (cookies_json, self.csrf_token))
            
            conn.commit()
            conn.close()
            
            ctx.log.info(f"[CookieCapture] 已保存 {len(self.cookies)} 个 Cookie 到数据库")
            ctx.log.info(f"[CookieCapture] Cookie keys: {list(self.cookies.keys())}")
            
        except Exception as e:
            ctx.log.error(f"[CookieCapture] 保存失败: {e}")


# 注册插件
addons = [CookieCaptureAddon()]
