"""
Audit logging module
Logs security-relevant events for compliance and monitoring
"""
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Create file handler if not exists
if not audit_logger.handlers:
    handler = logging.FileHandler("logs/audit.log")
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)


class AuditEventType(str, Enum):
    """Audit event types"""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"

    # Verification code events
    CODE_SENT = "verification_code_sent"
    CODE_VERIFIED = "verification_code_verified"
    CODE_FAILED = "verification_code_failed"

    # Session events
    SESSION_CREATED = "session_created"
    SESSION_INVALIDATED = "session_invalidated"
    SESSION_EXPIRED = "session_expired"

    # User events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    # Security events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class AuditService:
    """Service for audit logging"""

    @staticmethod
    def log_event(
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        phone: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """
        Log an audit event

        Args:
            event_type: Type of event
            user_id: User ID (if applicable)
            phone: Phone number (if applicable)
            ip_address: Client IP address
            details: Additional event details
            success: Whether the event was successful
        """
        event_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "success": success,
        }

        if user_id:
            event_data["user_id"] = user_id

        if phone:
            # Mask phone number for privacy (show only last 4 digits)
            masked_phone = f"***{phone[-4:]}" if len(phone) >= 4 else "***"
            event_data["phone"] = masked_phone

        if ip_address:
            event_data["ip_address"] = ip_address

        if details:
            event_data["details"] = details

        # Log as JSON for easy parsing
        audit_logger.info(json.dumps(event_data))

    @staticmethod
    def log_login_success(
        user_id: str,
        phone: str,
        ip_address: str,
        session_id: Optional[str] = None
    ) -> None:
        """Log successful login"""
        AuditService.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user_id,
            phone=phone,
            ip_address=ip_address,
            details={"session_id": session_id} if session_id else None,
            success=True
        )

    @staticmethod
    def log_login_failed(
        phone: str,
        ip_address: str,
        reason: str
    ) -> None:
        """Log failed login attempt"""
        AuditService.log_event(
            event_type=AuditEventType.LOGIN_FAILED,
            phone=phone,
            ip_address=ip_address,
            details={"reason": reason},
            success=False
        )

    @staticmethod
    def log_logout(
        user_id: str,
        session_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log logout event"""
        AuditService.log_event(
            event_type=AuditEventType.LOGOUT,
            user_id=user_id,
            ip_address=ip_address,
            details={"session_id": session_id},
            success=True
        )

    @staticmethod
    def log_code_sent(
        phone: str,
        ip_address: str
    ) -> None:
        """Log verification code sent"""
        AuditService.log_event(
            event_type=AuditEventType.CODE_SENT,
            phone=phone,
            ip_address=ip_address,
            success=True
        )

    @staticmethod
    def log_code_verified(
        phone: str,
        user_id: str,
        ip_address: str
    ) -> None:
        """Log verification code verified"""
        AuditService.log_event(
            event_type=AuditEventType.CODE_VERIFIED,
            phone=phone,
            user_id=user_id,
            ip_address=ip_address,
            success=True
        )

    @staticmethod
    def log_code_failed(
        phone: str,
        ip_address: str,
        attempts: int
    ) -> None:
        """Log verification code verification failed"""
        AuditService.log_event(
            event_type=AuditEventType.CODE_FAILED,
            phone=phone,
            ip_address=ip_address,
            details={"attempts": attempts},
            success=False
        )

    @staticmethod
    def log_rate_limit_exceeded(
        resource: str,
        identifier: str,
        ip_address: str
    ) -> None:
        """Log rate limit exceeded"""
        AuditService.log_event(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            ip_address=ip_address,
            details={"resource": resource, "identifier": identifier},
            success=False
        )

    @staticmethod
    def log_user_created(
        user_id: str,
        phone: str,
        ip_address: str
    ) -> None:
        """Log new user creation"""
        AuditService.log_event(
            event_type=AuditEventType.USER_CREATED,
            user_id=user_id,
            phone=phone,
            ip_address=ip_address,
            success=True
        )


# Create audit service instance
audit_service = AuditService()
