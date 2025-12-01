# core/validators.py

import re

def validate_and_fix_time(time_str: str):
    """
    Converts '8:5', '14.30', '۸:۳۰' -> '08:05', '14:30'
    Returns None if invalid.
    """
    if not time_str: return None
    
    # 1. Convert Persian/Arabic digits to English & standardize separator
    replacements = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '.': ':' # Allow dot as separator
    }
    for k, v in replacements.items():
        time_str = time_str.replace(k, v)
    
    # 2. Split and Validate
    try:
        parts = time_str.strip().split(':')
        if len(parts) != 2: return None
        
        h = int(parts[0])
        m = int(parts[1])
        
        if 0 <= h <= 23 and 0 <= m <= 59:
            # Format back to HH:MM (e.g. 8 -> 08)
            return f"{h:02}:{m:02}"
    except:
        pass
        
    # Failed validation
    return None