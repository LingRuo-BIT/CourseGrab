# -*- coding: utf-8 -*-
"""
代理管理服务
管理 mitmproxy 代理进程的启动和停止
"""

import os
import sys
import json
import subprocess
import threading
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path


class ProxyManager:
    """代理管理器"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.port = 8888
        self.addon_path = Path(__file__).parent / "proxy_addon.py"
        self._output_lines = []
        self._reader_thread: Optional[threading.Thread] = None
    
    def start(self, port: int = 8888) -> Dict[str, Any]:
        """启动代理"""
        if self.is_running:
            return {"success": False, "message": "代理已在运行"}
        
        self.port = port
        
        # 检查 mitmdump 是否可用
        try:
            result = subprocess.run(
                ["mitmdump", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return {
                    "success": False, 
                    "message": "mitmdump 不可用，请安装 mitmproxy: pip install mitmproxy"
                }
        except FileNotFoundError:
            return {
                "success": False, 
                "message": "未找到 mitmdump，请安装 mitmproxy: pip install mitmproxy"
            }
        
        # 启动代理进程
        try:
            cmd = [
                "mitmdump",
                "-s", str(self.addon_path),
                "-p", str(port),
                "--set", "block_global=false",
                "-q"  # 静默模式，只输出插件日志
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            self.is_running = True
            self._output_lines = []
            
            # 启动输出读取线程
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
            
            return {
                "success": True,
                "message": f"代理已启动在端口 {port}",
                "port": port,
                "instructions": [
                    f"1. 配置浏览器代理: HTTP 代理 -> localhost:{port}",
                    "2. 访问 https://jxzx.bit.edu.cn 并登录",
                    "3. 登录后 Cookie 将自动保存",
                    "4. 完成后可关闭代理"
                ]
            }
            
        except Exception as e:
            return {"success": False, "message": f"启动失败: {e}"}
    
    def stop(self) -> Dict[str, Any]:
        """停止代理"""
        if not self.is_running or not self.process:
            return {"success": False, "message": "代理未运行"}
        
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        
        self.is_running = False
        self.process = None
        
        return {"success": True, "message": "代理已停止"}
    
    def get_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        # 检查进程是否还在运行
        if self.process and self.process.poll() is not None:
            self.is_running = False
            self.process = None
        
        return {
            "is_running": self.is_running,
            "port": self.port if self.is_running else None,
            "recent_logs": self._output_lines[-20:] if self._output_lines else []
        }
    
    def _read_output(self):
        """读取进程输出"""
        if not self.process or not self.process.stdout:
            return
        
        try:
            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self._output_lines.append(line)
                    # 只保留最近100行
                    if len(self._output_lines) > 100:
                        self._output_lines = self._output_lines[-100:]
        except:
            pass


# 全局代理管理器实例
proxy_manager = ProxyManager()
