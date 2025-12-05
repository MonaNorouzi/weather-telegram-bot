# core/user_permission_service.py

from enum import Enum
from typing import Set
import logging

class UserTier(Enum):
    """Enum representing different user tiers/roles"""
    FREE = "free"
    PREMIUM = "premium"
    ADMIN = "admin"

class UserPermissionService:
    """
    Central service for managing user permissions and feature access.
    Uses Strategy Pattern to determine permissions based on user tier.
    """
    
    # Feature limits per tier
    SUBSCRIPTION_LIMITS = {
        UserTier.FREE: 3,
        UserTier.PREMIUM: 999,  # Effectively unlimited
        UserTier.ADMIN: 999
    }
    
    # Feature access matrix
    FEATURES = {
        "premium_support": [UserTier.PREMIUM, UserTier.ADMIN],
        "unlimited_cities": [UserTier.PREMIUM, UserTier.ADMIN],
        "priority_updates": [UserTier.PREMIUM, UserTier.ADMIN],
    }
    
    def __init__(self, premium_user_ids: Set[int], admin_id: int):
        """
        Initialize the permission service.
        
        Args:
            premium_user_ids: Set of user IDs that have premium access
            admin_id: The admin user ID
        """
        self.premium_user_ids = premium_user_ids
        self.admin_id = admin_id
        logging.info(f"🔐 UserPermissionService initialized: {len(premium_user_ids)} premium users")
    
    def get_user_tier(self, user_id: int) -> UserTier:
        """
        Determine the tier/role of a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            UserTier enum value
        """
        if user_id == self.admin_id:
            return UserTier.ADMIN
        if user_id in self.premium_user_ids:
            return UserTier.PREMIUM
        return UserTier.FREE
    
    def can_access_feature(self, user_id: int, feature_name: str) -> bool:
        """
        Check if a user can access a specific feature.
        
        Args:
            user_id: Telegram user ID
            feature_name: Name of the feature to check
            
        Returns:
            True if user has access, False otherwise
        """
        user_tier = self.get_user_tier(user_id)
        
        # If feature is not in the matrix, it's available to all
        if feature_name not in self.FEATURES:
            return True
        
        return user_tier in self.FEATURES[feature_name]
    
    def get_subscription_limit(self, user_id: int) -> int:
        """
        Get the maximum number of subscriptions allowed for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Maximum number of allowed subscriptions
        """
        user_tier = self.get_user_tier(user_id)
        return self.SUBSCRIPTION_LIMITS[user_tier]
    
    def can_add_subscription(self, user_id: int, current_count: int) -> bool:
        """
        Check if user can add another subscription.
        
        Args:
            user_id: Telegram user ID
            current_count: Current number of subscriptions
            
        Returns:
            True if user can add more, False otherwise
        """
        limit = self.get_subscription_limit(user_id)
        return current_count < limit
    
    def is_premium(self, user_id: int) -> bool:
        """
        Quick check if user has premium access (premium or admin).
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user is premium or admin, False otherwise
        """
        tier = self.get_user_tier(user_id)
        return tier in [UserTier.PREMIUM, UserTier.ADMIN]
