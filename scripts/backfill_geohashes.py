#!/usr/bin/env python3
"""
Geohash Backfill Script for Enterprise Migration

This script backfills geohash values for existing nodes and places in the database.
Uses batch processing (5000 rows per batch) to avoid locking tables and allow
concurrent reads during the migration.

Features:
- Batch processing with progress tracking
- Async execution for performance
- Graceful error handling
- Resume capability (skips already-filled rows)
- Detailed logging

Runtime: ~10-20 minutes for 100,000 nodes

Usage:
    python scripts/backfill_geohashes.py
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graph_database import graph_db
from core.geohash_utils import encode, PRECISION_NODE, PRECISION_PLACE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Batch configuration
BATCH_SIZE = 5000  # Rows per batch
COMMIT_PER_BATCH = True  # Commit after each batch (reduces lock time)


class GeohashBackfiller:
    """Handles backfilling geohashes for nodes and places."""
    
    def __init__(self):
        self.stats = {
            'nodes_total': 0,
            'nodes_updated': 0,
            'nodes_skipped': 0,
            'nodes_errors': 0,
            'places_total': 0,
            'places_updated': 0,
            'places_skipped': 0,
            'places_errors': 0,
        }
        self.start_time = None
    
    async def run(self):
        """Main backfill process."""
        logging.info("="*60)
        logging.info("GEOHASH BACKFILL STARTING")
        logging.info("="*60)
        self.start_time = datetime.now()
        
        try:
            # Initialize database
            await graph_db.initialize()
            
            # Backfill nodes (higher volume, precision 7)
            logging.info("\n📍 Backfilling NODES...")
            await self.backfill_nodes()
            
            # Backfill places (lower volume, precision 6)
            logging.info("\n🏙️  Backfilling PLACES...")
            await self.backfill_places()
            
            # Show final statistics
            self.print_statistics()
            
        except Exception as e:
            logging.error(f"❌ Backfill failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            await graph_db.close()
    
    async def backfill_nodes(self):
        """Backfill geohashes for nodes table."""
        async with graph_db.acquire() as conn:
            # Get total count
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM nodes WHERE geohash IS NULL"
            )
            self.stats['nodes_total'] = total
            
            if total == 0:
                logging.info("✅ All nodes already have geohashes")
                return
            
            logging.info(f"Found {total:,} nodes without geohashes")
            
            batch_num = 0
            offset = 0
            
            while True:
                batch_num += 1
                
                # Fetch batch of nodes without geohashes
                rows = await conn.fetch("""
                    SELECT node_id, ST_Y(geometry::geometry) as lat, ST_X(geometry::geometry) as lon
                    FROM nodes
                    WHERE geohash IS NULL
                    ORDER BY node_id
                    LIMIT $1
                """, BATCH_SIZE)
                
                if not rows:
                    break
                
                # Calculate geohashes in Python (faster than SQL)
                updates = []
                for row in rows:
                    try:
                        geohash = encode(row['lat'], row['lon'], precision=PRECISION_NODE)
                        if geohash:
                            updates.append((geohash, row['node_id']))
                        else:
                            self.stats['nodes_errors'] += 1
                            logging.warning(f"Failed to encode node_id={row['node_id']}")
                    except Exception as e:
                        self.stats['nodes_errors'] += 1
                        logging.error(f"Error encoding node_id={row['node_id']}: {e}")
                
                # Batch update
                if updates:
                    try:
                        await conn.executemany("""
                            UPDATE nodes SET geohash = $1 WHERE node_id = $2
                        """, updates)
                        
                        self.stats['nodes_updated'] += len(updates)
                        
                        # Log progress
                        progress_pct = (self.stats['nodes_updated'] / total) * 100
                        logging.info(
                            f"  Batch {batch_num}: Updated {len(updates):,} nodes "
                            f"({self.stats['nodes_updated']:,}/{total:,} = {progress_pct:.1f}%)"
                        )
                        
                    except Exception as e:
                        logging.error(f"❌ Batch update failed: {e}")
                        self.stats['nodes_errors'] += len(updates)
                
                offset += BATCH_SIZE
                
                # Small delay to avoid overwhelming the database
                await asyncio.sleep(0.1)
    
    async def backfill_places(self):
        """Backfill geohashes for places table."""
        async with graph_db.acquire() as conn:
            # Get total count
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM places WHERE geohash IS NULL"
            )
            self.stats['places_total'] = total
            
            if total == 0:
                logging.info("✅ All places already have geohashes")
                return
            
            logging.info(f"Found {total:,} places without geohashes")
            
            batch_num = 0
            
            while True:
                batch_num += 1
                
                # Fetch batch of places without geohashes
                rows = await conn.fetch("""
                    SELECT
                        place_id,
                        ST_Y(center_geom::geometry) as lat,
                        ST_X(center_geom::geometry) as lon
                    FROM places
                    WHERE geohash IS NULL AND center_geom IS NOT NULL
                    ORDER BY place_id
                    LIMIT $1
                """, BATCH_SIZE)
                
                if not rows:
                    break
                
                # Calculate geohashes (precision 6 for places)
                updates = []
                for row in rows:
                    try:
                        geohash = encode(row['lat'], row['lon'], precision=PRECISION_PLACE)
                        if geohash:
                            updates.append((geohash, row['place_id']))
                        else:
                            self.stats['places_errors'] += 1
                            logging.warning(f"Failed to encode place_id={row['place_id']}")
                    except Exception as e:
                        self.stats['places_errors'] += 1
                        logging.error(f"Error encoding place_id={row['place_id']}: {e}")
                
                # Batch update
                if updates:
                    try:
                        await conn.executemany("""
                            UPDATE places SET geohash = $1 WHERE place_id = $2
                        """, updates)
                        
                        self.stats['places_updated'] += len(updates)
                        
                        # Log progress
                        progress_pct = (self.stats['places_updated'] / total) * 100
                        logging.info(
                            f"  Batch {batch_num}: Updated {len(updates):,} places "
                            f"({self.stats['places_updated']:,}/{total:,} = {progress_pct:.1f}%)"
                        )
                        
                    except Exception as e:
                        logging.error(f"❌ Batch update failed: {e}")
                        self.stats['places_errors'] += len(updates)
                
                # Small delay
                await asyncio.sleep(0.1)
    
    def print_statistics(self):
        """Print final backfill statistics."""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        logging.info("\n" + "="*60)
        logging.info("GEOHASH BACKFILL COMPLETE")
        logging.info("="*60)
        
        logging.info(f"\n📊 NODES:")
        logging.info(f"   Total without geohash: {self.stats['nodes_total']:,}")
        logging.info(f"   Successfully updated:  {self.stats['nodes_updated']:,}")
        logging.info(f"   Errors:                {self.stats['nodes_errors']:,}")
        
        logging.info(f"\n🏙️  PLACES:")
        logging.info(f"   Total without geohash: {self.stats['places_total']:,}")
        logging.info(f"   Successfully updated:  {self.stats['places_updated']:,}")
        logging.info(f"   Errors:                {self.stats['places_errors']:,}")
        
        logging.info(f"\n⏱️  PERFORMANCE:")
        logging.info(f"   Duration:              {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        total_updated = self.stats['nodes_updated'] + self.stats['places_updated']
        if duration > 0:
            rate = total_updated / duration
            logging.info(f"   Update rate:           {rate:.0f} rows/second")
        
        logging.info("\n🎉 Backfill completed successfully!")
        logging.info("\nNext steps:")
        logging.info("1. Create indexes: See migrate_enterprise_spatial.sql Phase 4")
        logging.info("2. Restart application")
        logging.info("3. Run performance benchmarks\n")


async def main():
    """Entry point."""
    backfiller = GeohashBackfiller()
    await backfiller.run()


if __name__ == "__main__":
    asyncio.run(main())
