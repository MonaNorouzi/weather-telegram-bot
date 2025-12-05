# core/user_permission_service.py
"""User permission management service"""

from enum import Enum
from typing import Set
import logging


class UserTier(Enum):
    """User tier enum"""
    FREE = "free"
    PREMIUM = "premium"
    ADMIN = "admin"


class UserPermissionService:
    """Manages user permissions based on tier (Strategy Pattern)"""
    
    LIMITS = {UserTier.FREE: 3, UserTier.PREMIUM: 999, UserTier.ADMIN: 999}
    
    FEATURES = {
        "premium_support": [UserTier.PREMIUM, UserTier.ADMIN],
        "unlimited_cities": [UserTier.PREMIUM, UserTier.ADMIN],
    }
    
    def __init__(self, premium_ids: Set[int], admin_id: int):
        self.premium_user_ids = premium_ids
        self.admin_id = admin_id
        logging.info(f"🔐 Permission service: {len(premium_ids)} premium users")
    
    def get_user_tier(self, user_id: int) -> UserTier:
        """Get user's tier"""
        if user_id == self.admin_id:
            return UserTier.ADMIN
        if user_id in self.premium_user_ids:
            return UserTier.PREMIUM
        return UserTier.FREE
    
    def can_access_feature(self, user_id: int, feature: str) -> bool:
        """Check if user can access a feature"""
        tier = self.get_user_tier(user_id)
        if feature not in self.FEATURES:
            return True
        return tier in self.FEATURES[feature]
    
    def get_subscription_limit(self, user_id: int) -> int:
        """Get max subscriptions for user"""
        return self.LIMITS[self.get_user_tier(user_id)]
    
    def can_add_subscription(self, user_id: int, current: int) -> bool:
        """Check if user can add more subscriptions"""
        return current < self.get_subscription_limit(user_id)
    
    def is_premium(self, user_id: int) -> bool:
        """Check if user has premium access"""
        return self.get_user_tier(user_id) in [UserTier.PREMIUM, UserTier.ADMIN]
