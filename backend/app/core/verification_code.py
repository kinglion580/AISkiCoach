"""
验证码服务模块
提供验证码生成、存储、验证和发送功能
"""

import json
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import redis
from fastapi import HTTPException, status

from app.core.config import settings


class VerificationCodeService:
    """验证码服务类"""
    
    def __init__(self):
        self.redis_client = self._init_redis()
        self.prefix = "verification_code:"
        self.rate_limit_prefix = "rate_limit:"
        self.expire_seconds = settings.VERIFICATION_CODE_EXPIRE_MINUTES * 60
        self.max_attempts = settings.VERIFICATION_CODE_MAX_ATTEMPTS
        self.rate_limit_minutes = settings.VERIFICATION_CODE_RATE_LIMIT_MINUTES
        self.rate_limit_count = settings.VERIFICATION_CODE_RATE_LIMIT_COUNT
    
    def _init_redis(self) -> redis.Redis:
        """初始化Redis连接"""
        try:
            # 尝试连接Redis
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # 测试连接
            redis_client.ping()
            print("✅ Redis连接成功")
            return redis_client
        except Exception as e:
            # 开发环境如果Redis连接失败，使用内存Mock
            if settings.ENVIRONMENT == "local":
                print(f"⚠️  Redis连接失败，使用MockRedis: {str(e)}")
                return MockRedis()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Redis连接失败: {str(e)}"
            )
    
    def validate_phone(self, phone: str) -> bool:
        """验证手机号格式"""
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))
    
    def generate_code(self) -> str:
        """生成6位数字验证码"""
        return f"{secrets.randbelow(900000) + 100000:06d}"
    
    def check_rate_limit(self, phone: str) -> bool:
        """检查发送频率限制"""
        key = f"{self.rate_limit_prefix}{phone}"
        
        try:
            current = self.redis_client.incr(key)
            if current == 1:
                self.redis_client.expire(key, self.rate_limit_minutes * 60)
            return current <= self.rate_limit_count
        except Exception:
            # Redis错误时允许发送（开发环境容错）
            return True
    
    def store_code(self, phone: str, code: str) -> bool:
        """存储验证码"""
        key = f"{self.prefix}{phone}"
        data = {
            "code": code,
            "created_at": datetime.utcnow().isoformat(),
            "attempts": 0
        }
        try:
            return self.redis_client.setex(key, self.expire_seconds, json.dumps(data))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"验证码存储失败: {str(e)}"
            )
    
    def verify_code(self, phone: str, input_code: str) -> bool:
        """验证验证码"""
        key = f"{self.prefix}{phone}"
        try:
            data_str = self.redis_client.get(key)
            if not data_str:
                return False
            data = json.loads(data_str)
            if data["attempts"] >= self.max_attempts:
                self.redis_client.delete(key)
                return False
            if str(data["code"]) == str(input_code):
                self.redis_client.delete(key)
                return True
            data["attempts"] += 1
            self.redis_client.setex(key, self.expire_seconds, json.dumps(data))
            return False
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"验证码验证失败: {str(e)}"
            )
    
    def get_stored_code(self, phone: str) -> Optional[Dict[str, Any]]:
        """获取存储的验证码（开发环境使用）"""
        if settings.ENVIRONMENT != "local":
            return None
        key = f"{self.prefix}{phone}"
        try:
            data_str = self.redis_client.get(key)
            if data_str:
                return json.loads(data_str)
        except Exception:
            pass
        return None


class MockRedis:
    """Mock Redis类，用于开发环境没有Redis时"""
    
    def __init__(self):
        self.data = {}
    
    def setex(self, key: str, time: int, value: str) -> bool:
        self.data[key] = {
            "value": value,
            "expire_at": datetime.utcnow() + timedelta(seconds=time)
        }
        return True
    
    def get(self, key: str) -> Optional[str]:
        if key in self.data:
            item = self.data[key]
            if datetime.utcnow() < item["expire_at"]:
                return item["value"]
            else:
                del self.data[key]
        return None
    
    def delete(self, key: str) -> int:
        if key in self.data:
            del self.data[key]
            return 1
        return 0
    
    def incr(self, key: str) -> int:
        if key not in self.data:
            self.data[key] = {"value": "0", "expire_at": datetime.utcnow() + timedelta(hours=1)}
        current = int(self.data[key]["value"])
        current += 1
        self.data[key]["value"] = str(current)
        return current
    
    def expire(self, key: str, time: int) -> bool:
        if key in self.data:
            self.data[key]["expire_at"] = datetime.utcnow() + timedelta(seconds=time)
            return True
        return False


class SMSService:
    """短信服务类"""
    
    def __init__(self):
        self.service_type = settings.SMS_SERVICE
    
    def send_verification_code(self, phone: str, code: str) -> bool:
        """发送验证码短信"""
        if self.service_type == "mock":
            return self._mock_send(phone, code)
        elif self.service_type == "aliyun":
            return self._aliyun_send(phone, code)
        elif self.service_type == "tencent":
            return self._tencent_send(phone, code)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"不支持的短信服务类型: {self.service_type}"
            )
    
    def _mock_send(self, phone: str, code: str) -> bool:
        print(f"📱 [Mock SMS] 验证码发送到 {phone}: {code}")
        print(f"⏰ 验证码有效期: {settings.VERIFICATION_CODE_EXPIRE_MINUTES} 分钟")
        return True
    
    def _aliyun_send(self, phone: str, code: str) -> bool:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="阿里云短信服务暂未实现"
        )
    
    def _tencent_send(self, phone: str, code: str) -> bool:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="腾讯云短信服务暂未实现"
        )


# 全局实例
verification_code_service = VerificationCodeService()
sms_service = SMSService()


