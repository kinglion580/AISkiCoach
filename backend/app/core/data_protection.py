"""
Data protection utilities for masking sensitive information
Ensures sensitive data is properly masked in logs, API responses, and storage
"""
import re
from typing import Optional


class DataProtection:
    """Utility class for masking sensitive data"""

    @staticmethod
    def mask_phone(phone: str, show_last: int = 4) -> str:
        """
        Mask phone number showing only last N digits.

        Args:
            phone: Phone number to mask
            show_last: Number of digits to show at the end (default: 4)

        Returns:
            Masked phone number (e.g., "***1234")

        Examples:
            >>> DataProtection.mask_phone("13800138000")
            '***8000'
            >>> DataProtection.mask_phone("123")
            '***'
        """
        if not phone:
            return "***"

        clean_phone = re.sub(r'[^\d]', '', phone)
        if len(clean_phone) <= show_last:
            return "***"

        return f"***{clean_phone[-show_last:]}"

    @staticmethod
    def mask_email(email: str) -> str:
        """
        Mask email address showing only first character and domain.

        Args:
            email: Email address to mask

        Returns:
            Masked email (e.g., "u***@example.com")

        Examples:
            >>> DataProtection.mask_email("user@example.com")
            'u***@example.com'
        """
        if not email or '@' not in email:
            return "***"

        local, domain = email.split('@', 1)
        if len(local) <= 1:
            return f"***@{domain}"

        return f"{local[0]}***@{domain}"

    @staticmethod
    def mask_token(token: str, show_first: int = 10) -> str:
        """
        Mask token showing only first N characters.

        Args:
            token: Token to mask
            show_first: Number of characters to show at the start (default: 10)

        Returns:
            Masked token (e.g., "eyJhbGciOi...")

        Examples:
            >>> DataProtection.mask_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
            'eyJhbGciOi...'
        """
        if not token:
            return "***"

        if len(token) <= show_first:
            return token

        return f"{token[:show_first]}..."

    @staticmethod
    def mask_ip(ip: str, mask_last_octet: bool = True) -> str:
        """
        Mask IP address for privacy.

        Args:
            ip: IP address to mask
            mask_last_octet: If True, mask last octet (default: True)

        Returns:
            Masked IP (e.g., "192.168.1.***")

        Examples:
            >>> DataProtection.mask_ip("192.168.1.100")
            '192.168.1.***'
            >>> DataProtection.mask_ip("192.168.1.100", mask_last_octet=False)
            '192.168.1.100'
        """
        if not ip or not mask_last_octet:
            return ip

        # IPv4
        if '.' in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                return f"{'.'.join(parts[:3])}.***"

        # IPv6 - mask last segment
        if ':' in ip:
            parts = ip.split(':')
            if len(parts) >= 2:
                return f"{':'.join(parts[:-1])}:***"

        return ip

    @staticmethod
    def mask_credit_card(card: str) -> str:
        """
        Mask credit card number showing only last 4 digits.

        Args:
            card: Credit card number

        Returns:
            Masked card (e.g., "****-****-****-1234")

        Examples:
            >>> DataProtection.mask_credit_card("1234567890123456")
            '****-****-****-3456'
        """
        if not card:
            return "***"

        clean_card = re.sub(r'[^\d]', '', card)
        if len(clean_card) < 4:
            return "****-****-****-****"

        last_four = clean_card[-4:]
        return f"****-****-****-{last_four}"

    @staticmethod
    def should_mask_field(field_name: str) -> bool:
        """
        Determine if a field should be masked based on its name.

        Args:
            field_name: Name of the field

        Returns:
            True if field should be masked

        Examples:
            >>> DataProtection.should_mask_field("password")
            True
            >>> DataProtection.should_mask_field("username")
            False
        """
        sensitive_keywords = [
            'password', 'secret', 'token', 'key', 'credential',
            'authorization', 'auth', 'api_key', 'private'
        ]

        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in sensitive_keywords)

    @staticmethod
    def sanitize_dict(data: dict, mask_fields: Optional[list[str]] = None) -> dict:
        """
        Sanitize dictionary by masking sensitive fields.

        Args:
            data: Dictionary to sanitize
            mask_fields: List of field names to mask (optional)

        Returns:
            Sanitized dictionary with masked sensitive fields

        Examples:
            >>> DataProtection.sanitize_dict({"phone": "13800138000", "name": "User"})
            {'phone': '***8000', 'name': 'User'}
        """
        if mask_fields is None:
            mask_fields = ['phone', 'email', 'password', 'token']

        sanitized = {}
        for key, value in data.items():
            if key in mask_fields or DataProtection.should_mask_field(key):
                # Determine masking strategy based on field name
                if 'phone' in key.lower():
                    sanitized[key] = DataProtection.mask_phone(str(value)) if value else None
                elif 'email' in key.lower():
                    sanitized[key] = DataProtection.mask_email(str(value)) if value else None
                elif 'token' in key.lower() or 'key' in key.lower():
                    sanitized[key] = DataProtection.mask_token(str(value)) if value else None
                elif 'password' in key.lower() or 'secret' in key.lower():
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = "***"
            else:
                sanitized[key] = value

        return sanitized
