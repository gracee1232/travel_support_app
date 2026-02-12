"""
Local Database Service.
Handles interactions with local SQLite datasets for trusted travel data.
"""
import sqlite3
import logging
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

import re

def _is_latin_text(text: str) -> bool:
    """Check if text is primarily Latin script (English). Rejects Arabic, Cyrillic, CJK, etc."""
    if not text:
        return False
    # Count Latin characters vs total alphabetic characters
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total_alpha = len(re.findall(r'[^\s\d\W]', text, re.UNICODE))
    if total_alpha == 0:
        return False
    return (latin_chars / total_alpha) > 0.5

class LocalDatabaseService:
    """Service to interact with local hospitality databases."""
    
    def __init__(self):
        # Paths to the databases
        # Current file: .../travel_support_app/app/services/local_database.py
        # root (chatbot): .../
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_domestic = os.path.join(base_dir, "dataset", "hospitality_dataset.db")
        self.db_intl = os.path.join(base_dir, "dataset", "hospitality_dataset_intl.db")
        
        # Verify existence
        if not os.path.exists(self.db_domestic):
            logger.warning(f"Domestic DB not found at {self.db_domestic}")
        if not os.path.exists(self.db_intl):
            logger.warning(f"International DB not found at {self.db_intl}")

    def _get_connection(self, db_path: str) -> Optional[sqlite3.Connection]:
        """Create a database connection."""
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                return conn
        except Exception as e:
            logger.error(f"Error connecting to DB {db_path}: {e}")
        return None

    def _query_db(self, db_path: str, query: str, args: Tuple = ()) -> List[Dict]:
        """Execute a query against a specific database."""
        conn = self._get_connection(db_path)
        if not conn:
            return []
        
        try:
            cursor = conn.execute(query, args)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query error in {db_path}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_city_status(self, city_name: str) -> Dict[str, bool]:
        """
        Check if a city exists in either database.
        Returns: {'found': bool, 'is_domestic': bool, 'is_intl': bool}
        """
        query = "SELECT name FROM cities WHERE name LIKE ? LIMIT 1"
        args = (f"{city_name}%",) # Flexible matching
        
        domestic_res = self._query_db(self.db_domestic, query, args)
        intl_res = self._query_db(self.db_intl, query, args)
        
        return {
            "found": bool(domestic_res or intl_res),
            "is_domestic": bool(domestic_res),
            "is_intl": bool(intl_res),
            "official_name": (domestic_res[0]['name'] if domestic_res else (intl_res[0]['name'] if intl_res else None))
        }

    def get_hotels(self, city_name: str, budget: str = "standard") -> List[Dict]:
        """Fetch hotels for a city from local DBs."""
        status = self.get_city_status(city_name)
        if not status['found']:
            return []
            
        target_name = status['official_name']
        query = "SELECT * FROM hotels WHERE city_name = ?"
        
        results = []
        if status['is_domestic']:
            results.extend(self._query_db(self.db_domestic, query, (target_name,)))
        if status['is_intl']:
            results.extend(self._query_db(self.db_intl, query, (target_name,)))
            
        # Basic client-side filtering
        final_results = []
        for r in results:
            name = r.get('name', '')
            
            # Skip non-Latin names (Arabic, Cyrillic, etc.)
            if not _is_latin_text(name):
                continue
            
            # Exclude obvious non-hotels if any sneak in
            if any(x in name.lower() for x in ['sweet', 'store', 'shop']):
                continue
                
            final_results.append(r)
            
        return final_results

    def get_restaurants(self, city_name: str) -> List[Dict]:
        """Fetch restaurants for a city."""
        status = self.get_city_status(city_name)
        if not status['found']:
            return []
            
        target_name = status['official_name']
        query = "SELECT * FROM restaurants WHERE city_name = ?"
        
        results = []
        if status['is_domestic']:
            results.extend(self._query_db(self.db_domestic, query, (target_name,)))
        if status['is_intl']:
            results.extend(self._query_db(self.db_intl, query, (target_name,)))
        
        # Filter out non-Latin names
        return [r for r in results if _is_latin_text(r.get('name', ''))]

    def get_areas(self, city_name: str) -> List[Dict]:
        """Fetch areas/attractions for a city."""
        status = self.get_city_status(city_name)
        if not status['found']:
            return []
            
        target_name = status['official_name']
        query = "SELECT * FROM areas WHERE city_name = ?"
        
        results = []
        if status['is_domestic']:
            results.extend(self._query_db(self.db_domestic, query, (target_name,)))
        if status['is_intl']:
            results.extend(self._query_db(self.db_intl, query, (target_name,)))
            
        # Refined Filtering: Remove boring residential areas AND non-Latin names
        filtered = []
        for r in results:
            name = r.get('name', '')
            t = r.get('type', '').lower()
            tags = r.get('tags', '').lower()
            
            # Skip non-Latin names (Arabic, Cyrillic, etc.)
            if not _is_latin_text(name):
                continue
            
            # Whitelist interesting types
            is_interesting = any(x in t for x in ['museum', 'park', 'attraction', 'viewpoint', 'historic', 'monument', 'temple', 'church', 'zoo', 'garden'])
            # Whitelist interesting tags
            has_good_tags = any(x in tags for x in ['tourism', 'historic', 'culture', 'nature', 'landmark', 'art'])
            
            # Blacklist residential unless they have good tags
            is_boring = t in ['neighbourhood', 'suburb', 'residential', 'locality']
            
            if is_interesting or has_good_tags or not is_boring:
                filtered.append(r)
        
        # Fallback: If we filtered everything out, 
        # return top 5 Latin-named results so the LLM has SOMETHING to work with.
        if not filtered and results:
             latin_results = [r for r in results if _is_latin_text(r.get('name', ''))]
             return latin_results[:5] if latin_results else results[:5]
                
        return filtered

    def get_coordinates(self, place_name: str) -> Optional[List[float]]:
        """
        Get [lon, lat] for a place name using Local DB.
        Returns: [lon, lat] or None
        """
        # Try finding in hotels
        query_hotel = "SELECT lat, lon FROM hotels WHERE name LIKE ? LIMIT 1"
        res = self._query_db(self.db_domestic, query_hotel, (f"%{place_name}%",))
        if not res:
            res = self._query_db(self.db_intl, query_hotel, (f"%{place_name}%",))
            
        if res:
            return [res[0]['lon'], res[0]['lat']]

        # Try finding in restaurants
        query_rest = "SELECT lat, lon FROM restaurants WHERE name LIKE ? LIMIT 1"
        res = self._query_db(self.db_domestic, query_rest, (f"%{place_name}%",))
        if not res:
            res = self._query_db(self.db_intl, query_rest, (f"%{place_name}%",))
            
        if res:
            return [res[0]['lon'], res[0]['lat']]
            
        # Try finding in areas (if they had lat/lon, but schema didn't show it. 
        # Assuming cities table has it for the city center)
        # Check if it is a city name
        query_city = "SELECT lat, lon FROM cities WHERE name LIKE ? LIMIT 1"
        res = self._query_db(self.db_domestic, query_city, (f"{place_name}",))
        if not res:
            res = self._query_db(self.db_intl, query_city, (f"{place_name}",))
            
        if res:
            return [res[0]['lon'], res[0]['lat']]
            
        return None

# Global instance
local_db = LocalDatabaseService()
