# core/overpass_service.py
"""Overpass API - Batch processing with retry logic for maximum reliability"""

import aiohttp
import asyncio
import logging
import config
from typing import List, Dict
from core.route_sampler import sample_by_distance


class OverpassService:
    BASE_URL = "https://overpass-api.de/api/interpreter"
    
    # Manager's proven parameters - exactly as tested
    SEARCH_RADIUS = 3000      # 3km radius - focus on major places only
    BATCH_SIZE = 20           # 20 points per batch (larger for speed)
    MAX_RETRIES = 5           # Maximum retry attempts per batch
    CONCURRENCY = 1           # Reduced to 1 to avoid rate limiting
    SAMPLE_INTERVAL_KM = 20.0  # 20km for long routes (less API load)
    REQUEST_DELAY = 0.8       # Delay between batches (slightly longer)
    QUERY_TIMEOUT = 90        # Overpass query timeout in seconds
    
    async def get_places_along_route(self, coordinates: List[List[float]]) -> List[Dict]:
        """Get ALL places along route using proven batch + retry strategy
        
        This implementation combines:
        - Distance-based sampling (every 5km) for consistent coverage
        - Batch processing (15 points per batch) for API efficiency
        - Retry logic with exponential backoff for reliability
        - Concurrent processing for speed
        
        Args:
            coordinates: Full list of [lon, lat] pairs from OSRM
            
        Returns:
            List of unique place dictionaries with name, type, lat, lon
        """
        # Step 1: Sample route by distance (not by index)
        sampled = sample_by_distance(coordinates, interval_km=self.SAMPLE_INTERVAL_KM)
        logging.info(f"Overpass: Processing {len(sampled)} sample points (every {self.SAMPLE_INTERVAL_KM}km)")
        
        # Step 2: Split into batches
        batches = [sampled[i:i + self.BATCH_SIZE] 
                   for i in range(0, len(sampled), self.BATCH_SIZE)]
        logging.info(f"Overpass: Split into {len(batches)} batches of ~{self.BATCH_SIZE} points")
        
        # Step 3: Process batches concurrently with rate limiting
        semaphore = asyncio.Semaphore(self.CONCURRENCY)
        tasks = [
            self._fetch_batch_with_retry(batch, semaphore, idx + 1)
            for idx, batch in enumerate(batches)
        ]
        
        batch_results = await asyncio.gather(*tasks)
        
        # Step 4: Aggregate all results
        all_places = []
        for result in batch_results:
            all_places.extend(result)
        
        logging.info(f"Overpass: Aggregated {len(all_places)} total places")
        
        # Step 5: Deduplicate
        unique_places = self._deduplicate(all_places)
        logging.info(f"Overpass: {len(unique_places)} unique places after deduplication")
        
        return unique_places
    
    async def _fetch_batch_with_retry(self, coords_batch: List[List[float]], 
                                       semaphore: asyncio.Semaphore, 
                                       batch_id: int) -> List[Dict]:
        """Fetch one batch with exponential backoff retry logic
        
        Args:
            coords_batch: List of [lon, lat] pairs for this batch
            semaphore: Concurrency limiter
            batch_id: Batch identifier for logging
            
        Returns:
            List of places found in this batch
        """
        attempt = 0
        wait_time = 2.0
        
        async with semaphore:
            while attempt < self.MAX_RETRIES:
                try:
                    # Rate limiting delay between batches
                    await asyncio.sleep(self.REQUEST_DELAY)
                    
                    # Build Overpass query - EXACT format as manager's code
                    coord_str = ",".join([f"{lat},{lon}" for lon, lat in coords_batch])
                    
                    # Single-line query format (matches manager's routing.py line 65)
                    query = f"""[out:json][timeout:{self.QUERY_TIMEOUT}];node["place"~"city|town|village|hamlet|suburb|isolated_dwelling"](around:{self.SEARCH_RADIUS},{coord_str});out body;"""
                    
                    timeout = aiohttp.ClientTimeout(total=120)
                    async with aiohttp.ClientSession(timeout=timeout) as sess:
                        async with sess.post(self.BASE_URL, data=query, proxy=config.PROXY_URL) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                places = self._parse_elements(data.get("elements", []))
                                logging.info(f"Batch {batch_id}: SUCCESS - {len(places)} places")
                                return places
                            
                            elif resp.status == 429:
                                # Rate limited - exponential backoff
                                logging.warning(f"Batch {batch_id}: Rate limited (429), waiting {wait_time:.1f}s...")
                                await asyncio.sleep(wait_time)
                                wait_time *= 2  # Exponential backoff
                                attempt += 1
                            
                            else:
                                # Other error - retry with delay
                                logging.warning(f"Batch {batch_id}: HTTP {resp.status}, retry {attempt + 1}/{self.MAX_RETRIES}")
                                await asyncio.sleep(wait_time)
                                attempt += 1
                
                except Exception as e:
                    logging.error(f"Batch {batch_id}: Error - {e}, retry {attempt + 1}/{self.MAX_RETRIES}")
                    await asyncio.sleep(wait_time)
                    attempt += 1
        
        # All retries exhausted
        logging.error(f"Batch {batch_id}: FAILED after {self.MAX_RETRIES} attempts")
        return []
    
    def _parse_elements(self, elements: List[Dict]) -> List[Dict]:
        """Parse Overpass XML elements into standardized format
        
        Args:
            elements: Raw elements from Overpass response
            
        Returns:
            List of parsed place dictionaries
        """
        places = []
        for el in elements:
            if el.get("type") != "node":
                continue
            
            tags = el.get("tags", {})
            
            # Try multiple name fields (support for Persian/English names)
            name = (tags.get("name:fa") or tags.get("name") or 
                    tags.get("name:en") or tags.get("alt_name"))
            
            if not name:
                continue
            
            places.append({
                "name": name,
                "type": tags.get("place", "unknown"),
                "lat": el["lat"],
                "lon": el["lon"]
            })
        
        return places
    
    def _deduplicate(self, places: List[Dict]) -> List[Dict]:
        """Remove duplicate places while preserving order
        
        Uses name and rounded coordinates as deduplication key
        
        Args:
            places: List of place dictionaries
            
        Returns:
            List of unique places
        """
        seen = set()
        unique = []
        
        for p in places:
            # Use 4 decimal places (~10m precision) for coordinate rounding
            key = (p["name"], round(p["lat"], 4), round(p["lon"], 4))
            
            if key not in seen:
                seen.add(key)
                unique.append(p)
        
        return unique


    # City boundary fetching (separate from route places)
    async def get_city_boundary(self, city_name: str, country: str = "Iran"):
        """Get administrative boundary polygon for a city.
        
        Args:
            city_name: City name
            country: Country for disambiguation
            
        Returns:
            Dict with coordinates, center, osm_id, admin_level
        """
        from core.boundary_fetcher import get_city_boundary
        return await get_city_boundary(city_name, country)


overpass_service = OverpassService()

