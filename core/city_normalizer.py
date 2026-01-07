"""City Name Normalizer - Convert any city name to canonical English format.

This service ensures consistent cache keys across different languages/scripts:
- تهران → tehran
- Tehran → tehran  
- MASHHAD → mashhad

Cache uses normalized (English) names, but displays use original user input.
"""

import unicodedata
import re
from typing import Dict, Optional

class CityNameNormalizer:
    """Normalize city names to canonical English lowercase format"""
    
    # Common Persian→English mappings for major cities
    KNOWN_TRANSLATIONS = {
        'تهران': 'tehran',
        'مشهد': 'mashhad',
        'اصفهان': 'isfahan',
        'شیراز': 'shiraz',
        'تبریز': 'tabriz',
        'کرج': 'karaj',
        'قم': 'qom',
        'اهواز': 'ahvaz',
        'کرمانشاه': 'kermanshah',
        'ارومیه': 'urmia',
        'رشت': 'rasht',
        'کرمان': 'kerman',
        'همدان': 'hamedan',
        'اردبیل': 'ardabil',
        'یزد': 'yazd',
        'قزوین': 'qazvin',
        'زنجان': 'zanjan',
        'سنندج': 'sanandaj',
        'بندرعباس': 'bandarabbas',
        'گرگان': 'gorgan',
        'ساری': 'sari',
        'بیرجند': 'birjand',
        'بوشهر': 'bushehr',
        'ایلام': 'ilam',
        'سمنان': 'semnan',
        'خرم‌آباد': 'khorramabad',
        'یاسوج': 'yasuj',
        'شهرکرد': 'shahrekord',
    }
    
    @classmethod
    def normalize(cls, city_name: str) -> str:
        """Convert city name to normalized English lowercase.
        
        Args:
            city_name: City name in any language/script
            
        Returns:
            Normalized English lowercase name (e.g., 'tehran')
        """
        if not city_name:
            return ""
        
        # Trim and normalize whitespace
        city_name = city_name.strip()
        
        # Check known translations first (for accurate Persian→English)
        city_lower = city_name.lower()
        if city_lower in cls.KNOWN_TRANSLATIONS:
            return cls.KNOWN_TRANSLATIONS[city_lower]
        
        # For English or unknown names, normalize
        # 1. Remove diacritics (é → e, ñ → n)
        normalized = unicodedata.normalize('NFKD', city_name)
        normalized = normalized.encode('ascii', 'ignore').decode('ascii')
        
        # 2. Lowercase
        normalized = normalized.lower()
        
        # 3. Remove special characters, keep only alphanumeric and spaces
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        
        # 4. Replace spaces with empty (or underscore if preferred)
        normalized = re.sub(r'\s+', '', normalized)
        
        return normalized
    
    @classmethod
    def add_translation(cls, persian: str, english: str):
        """Add a new Persian→English translation to the known mappings.
        
        Args:
            persian: City name in Persian
            english: Normalized English name
        """
        cls.KNOWN_TRANSLATIONS[persian.lower()] = english.lower()


# Global instance
city_normalizer = CityNameNormalizer()


# Testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        ('تهران', 'tehran'),
        ('Tehran', 'tehran'),
        ('TEHRAN', 'tehran'),
        ('مشهد', 'mashhad'),
        ('Mashhad', 'mashhad'),
        ('قم', 'qom'),
        ('Qom', 'qom'),
    ]
    
    print("Testing City Name Normalizer:")
    for input_name, expected in test_cases:
        result = city_normalizer.normalize(input_name)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_name:15} → {result:15} (expected: {expected})")
