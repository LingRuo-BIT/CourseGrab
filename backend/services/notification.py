# -*- coding: utf-8 -*-
"""
通知服务
支持邮件和企业微信机器人通知
"""

import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
import aiohttp
from datetime import datetime

from config import settings


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
    
    async def send(
        self,
        to: str,
        subject: str,
        content: str,
        content_type: str = "html"
    ) -> bool:
        """
        发送邮件
        
        Args:
            to: 收件人邮箱（多个用逗号分隔）
            subject: 邮件主题
            content: 邮件内容
            content_type: 内容类型，"html" 或 "plain"
        
        Returns:
            是否发送成功
        """
        try:
            # 创建邮件
            message = MIMEMultipart("alternative")
            message["From"] = self.username
            message["To"] = to
            message["Subject"] = subject
            
            # 添加内容
            part = MIMEText(content, content_type, "utf-8")
            message.attach(part)
            
            # 发送
            if self.use_ssl:
                await aiosmtplib.send(
                    message,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.username,
                    password=self.password,
                    use_tls=True,
                )
            else:
                await aiosmtplib.send(
                    message,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.username,
                    password=self.password,
                    start_tls=True,
                )
            
            return True
        except Exception as e:
            print(f"邮件发送失败: {e}")
            return False


class WeComBotNotifier:
    """企业微信机器人通知器"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_text(
        self,
        content: str,
        mentioned_list: Optional[List[str]] = None,
        mentioned_mobile_list: Optional[List[str]] = None,
    ) -> bool:
        """
        发送文本消息
        
        Args:
            content: 消息内容
            mentioned_list: @的用户ID列表
            mentioned_mobile_list: @的手机号列表
        
        Returns:
            是否发送成功
        """
        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
            }
        }
        
        if mentioned_list:
            payload["text"]["mentioned_list"] = mentioned_list
        if mentioned_mobile_list:
            payload["text"]["mentioned_mobile_list"] = mentioned_mobile_list
        
        return await self._send(payload)
    
    async def send_markdown(self, content: str) -> bool:
        """
        发送 Markdown 消息
        
        Args:
            content: Markdown 格式的消息内容
        
        Returns:
            是否发送成功
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        return await self._send(payload)
    
    async def _send(self, payload: dict) -> bool:
        """发送消息到 Webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    return result.get("errcode", -1) == 0
        except Exception as e:
            print(f"企业微信消息发送失败: {e}")
            return False


class NotificationService:
    """统一通知服务"""
    
    def __init__(
        self,
        email_config: Optional[dict] = None,
        wecom_config: Optional[dict] = None,
    ):
        self.email_notifier = None
        self.wecom_notifier = None
        
        if email_config and email_config.get("enabled"):
            self.email_notifier = EmailNotifier(
                smtp_host=email_config.get("smtp_host", ""),
                smtp_port=email_config.get("smtp_port", 465),
                username=email_config.get("username", ""),
                password=email_config.get("password", ""),
            )
            self.email_to = email_config.get("to", "")
        
        if wecom_config and wecom_config.get("enabled"):
            self.wecom_notifier = WeComBotNotifier(
                webhook_url=wecom_config.get("webhook", "")
            )
    
    async def notify_grab_success(
        self,
        kcmc: str,
        bjmc: str,
        rkjs: str,
        pksj: str,
        pkdd: str,
    ) -> dict:
        """
        发送抢课成功通知
        
        Returns:
            {"email": True/False, "wecom": True/False}
        """
        results = {"email": False, "wecom": False}
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 邮件通知
        if self.email_notifier and self.email_to:
            subject = f"🎉 抢课成功 - {kcmc}"
            content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #28a745;">🎉 抢课成功通知</h2>
                <table style="border-collapse: collapse; width: 100%; max-width: 500px;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>课程名称</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{kcmc}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>班级</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{bjmc}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>教师</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{rkjs}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>时间</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{pksj}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>地点</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">{pkdd}</td>
                    </tr>
                </table>
                <p style="color: #666; margin-top: 20px;">抢课时间: {now}</p>
            </body>
            </html>
            """
            results["email"] = await self.email_notifier.send(
                to=self.email_to,
                subject=subject,
                content=content,
            )
        
        # 企业微信通知
        if self.wecom_notifier:
            content = f"""## 🎉 抢课成功通知

**课程名称**: {kcmc}
**班级**: {bjmc}
**教师**: {rkjs}
**时间**: {pksj}
**地点**: {pkdd}

> 抢课时间: {now}"""
            
            results["wecom"] = await self.wecom_notifier.send_markdown(content)
        
        return results
    
    async def notify_grab_failed(
        self,
        kcmc: str,
        bjmc: str,
        error_msg: str,
    ) -> dict:
        """发送抢课失败通知"""
        results = {"email": False, "wecom": False}
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 企业微信通知
        if self.wecom_notifier:
            content = f"""## ⚠️ 抢课失败通知

**课程名称**: {kcmc}
**班级**: {bjmc}
**失败原因**: {error_msg}

> 时间: {now}"""
            
            results["wecom"] = await self.wecom_notifier.send_markdown(content)
        
        return results
    
    async def test_notification(self) -> dict:
        """测试通知配置"""
        results = {"email": False, "wecom": False}
        
        # 测试邮件
        if self.email_notifier and self.email_to:
            results["email"] = await self.email_notifier.send(
                to=self.email_to,
                subject="CourseGrab 通知测试",
                content="<p>这是一封测试邮件，如果您收到此邮件，说明邮件通知配置正确。</p>",
            )
        
        # 测试企业微信
        if self.wecom_notifier:
            results["wecom"] = await self.wecom_notifier.send_markdown(
                "## 🔔 CourseGrab 通知测试\n\n这是一条测试消息，如果您收到此消息，说明企业微信通知配置正确。"
            )
        
        return results
