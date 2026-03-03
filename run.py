#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CourseGrab 启动脚本
一键启动后端服务
"""

import os
import sys
import uvicorn

# 确保 backend 目录在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def main():
    """启动服务"""
    print("=" * 50)
    print("  CourseGrab - BIT 辅助抢课系统")
    print("=" * 50)
    print()
    print("正在启动服务...")
    print("访问地址: http://localhost:8000")
    print()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["backend"],
    )

if __name__ == "__main__":
    main()
