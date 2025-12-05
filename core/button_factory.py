# core/button_factory.py

from telethon import Button
from typing import List
from core.user_permission_service import UserPermissionService

class ButtonFactory:
    """
    Factory Pattern for creating dynamic button layouts based on user permissions.
    Centralizes button creation logic for maintainability and consistency.
    """
    
    def __init__(self, permission_service: UserPermissionService):
        """
        Initialize the button factory.
        
        Args:
            permission_service: UserPermissionService instance for permission checks
        """
        self.permission_service = permission_service
    
    def create_settings_buttons(self, user_id: int, subscriptions: list) -> List[List[Button]]:
        """
        Generate dynamic settings menu buttons based on user tier and subscriptions.
        
        Args:
            user_id: Telegram user ID
            subscriptions: List of user's current subscriptions
            
        Returns:
            List of button rows for the settings menu
        """
        buttons = []
        current_count = len(subscriptions)
        
        # Show all subscriptions with delete buttons
        if subscriptions:
            for sub in subscriptions:
                btn_text = f"🗑 {sub['city_name']} ({sub['schedule_time']})"
                btn_data = f"del_{sub['id']}".encode()
                buttons.append([Button.inline(btn_text, btn_data)])
        else:
            # Empty state
            buttons.append([Button.inline("📭 Your list is empty", b"ignore")])
        
        # Add New City button or Upgrade prompt
        can_add = self.permission_service.can_add_subscription(user_id, current_count)
        
        if can_add:
            buttons.append([Button.inline("➕ Add New City", b"add_city_start")])
        else:
            # User hit limit - show upgrade prompt for free users
            if not self.permission_service.is_premium(user_id):
                limit = self.permission_service.get_subscription_limit(user_id)
                buttons.append([
                    Button.inline(f"⭐ Upgrade to Premium (Limit: {limit}/{limit})", b"upgrade_premium")
                ])
        
        # Premium-only features
        if self.permission_service.can_access_feature(user_id, "premium_support"):
            buttons.append([Button.inline("🌟 Premium Support", b"premium_support")])
        
        # Close button (available to all)
        buttons.append([Button.inline("❌ Close Menu", b"cancel_action")])
        
        return buttons
    
    def create_subscription_list_buttons(self, user_id: int, subscriptions: list) -> List[List[Button]]:
        """
        Generate subscription list buttons.
        
        Args:
            user_id: Telegram user ID
            subscriptions: List of user's subscriptions
            
        Returns:
            List of button rows
        """
        buttons = []
        
        for sub in subscriptions:
            btn_text = f"📍 {sub['city_name']} - {sub['schedule_time']}"
            btn_data = f"view_{sub['id']}".encode()
            buttons.append([Button.inline(btn_text, btn_data)])
        
        return buttons
    
    def create_premium_upsell_button(self) -> List[List[Button]]:
        """
        Create premium upgrade promotional button.
        
        Returns:
            Button row with upgrade option
        """
        return [[Button.inline("⭐ Upgrade to Premium", b"upgrade_premium")]]
    
    def get_limit_info_text(self, user_id: int, current_count: int) -> str:
        """
        Get formatted text showing subscription limits.
        
        Args:
            user_id: Telegram user ID
            current_count: Current number of subscriptions
            
        Returns:
            Formatted string with limit information
        """
        limit = self.permission_service.get_subscription_limit(user_id)
        tier = self.permission_service.get_user_tier(user_id)
        
        if limit >= 999:  # Unlimited
            return f"🌟 **{tier.value.title()}**: Unlimited cities ({current_count} active)"
        else:
            return f"📊 **Cities**: {current_count}/{limit}"
