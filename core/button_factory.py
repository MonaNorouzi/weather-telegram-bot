# core/button_factory.py
"""Dynamic button factory based on user permissions"""

from telethon import Button
from typing import List
from core.user_permission_service import UserPermissionService


class ButtonFactory:
    """Creates dynamic button layouts based on user permissions (Factory Pattern)"""
    
    def __init__(self, permission_service: UserPermissionService):
        self.ps = permission_service
    
    def create_settings_buttons(self, user_id: int, subs: list) -> List[List[Button]]:
        """Generate settings menu buttons"""
        buttons = []
        count = len(subs)
        
        # Subscription delete buttons
        if subs:
            for sub in subs:
                text = f"🗑 {sub['city_name']} ({sub['schedule_time']})"
                buttons.append([Button.inline(text, f"del_{sub['id']}".encode())])
        else:
            buttons.append([Button.inline("📭 Your list is empty", b"ignore")])
        
        # Add city or upgrade button
        if self.ps.can_add_subscription(user_id, count):
            buttons.append([Button.inline("➕ Add New City", b"add_city_start")])
        elif not self.ps.is_premium(user_id):
            limit = self.ps.get_subscription_limit(user_id)
            buttons.append([Button.inline(f"⭐ Upgrade ({limit}/{limit})", b"upgrade_premium")])
        
        # Premium-only button
        if self.ps.can_access_feature(user_id, "premium_support"):
            buttons.append([Button.inline("🌟 Premium Support", b"premium_support")])
        
        buttons.append([Button.inline("❌ Close Menu", b"cancel_action")])
        return buttons
    
    def get_limit_info_text(self, user_id: int, count: int) -> str:
        """Get limit info text"""
        limit = self.ps.get_subscription_limit(user_id)
        tier = self.ps.get_user_tier(user_id)
        
        if limit >= 999:
            return f"🌟 **{tier.value.title()}**: Unlimited ({count} active)"
        return f"📊 **Cities**: {count}/{limit}"
