# core/route_data_saver.py
"""Save detailed route data to JSON for future use"""

import json
import os
from datetime import datetime
from typing import Dict, List

ROUTE_DATA_DIR = "route_data"

def ensure_data_dir():
    """Create route_data directory if it doesn't exist"""
    if not os.path.exists(ROUTE_DATA_DIR):
        os.makedirs(ROUTE_DATA_DIR)

def save_route_json(
    user_id: int,
    origin_name: str,
    dest_name: str,
    start_time: str,
    schedule: List[Dict],
    with_traffic: bool
) -> str:
    """Save detailed route data to JSON file"""
    ensure_data_dir()
    
    # Find coldest and warmest
    temps = [s.get("temperature_celsius", 0) for s in schedule if s.get("temperature_celsius")]
    coldest = min(temps) if temps else None
    warmest = max(temps) if temps else None
    
    # Calculate estimated arrival
    if schedule:
        last = schedule[-1]
        est_arrival = last.get("arrival_time", "")
    else:
        est_arrival = ""
    
    data = {
        "meta": {
            "user_id": user_id,
            "origin": origin_name,
            "destination": dest_name,
            "start_time": start_time,
            "estimated_arrival": est_arrival,
            "with_traffic_buffer": with_traffic,
            "coldest_celsius": coldest,
            "warmest_celsius": warmest,
            "generated_at": datetime.now().isoformat()
        },
        "schedule": schedule
    }
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"route_{user_id}_{timestamp}.json"
    filepath = os.path.join(ROUTE_DATA_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    return filepath

def get_coldest_warmest(schedule: List[Dict]) -> tuple:
    """Get coldest and warmest places from schedule"""
    if not schedule:
        return None, None
    
    # Filter only places with valid temperatures
    valid_temps = [s for s in schedule if s.get("temperature_celsius") is not None]
    
    if not valid_temps:
        return None, None
    
    coldest_place = min(valid_temps, key=lambda x: x.get("temperature_celsius"))
    warmest_place = max(valid_temps, key=lambda x: x.get("temperature_celsius"))
    
    return coldest_place, warmest_place
