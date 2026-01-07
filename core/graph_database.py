# core/graph_database.py
"""Graph Database Manager with connection pooling for PostgreSQL + PostGIS + pgRouting."""

import asyncpg
import logging
import os
from typing import Optional
from contextlib import asynccontextmanager

class GraphDatabaseManager:
    """Manages PostgreSQL connection pool and provides database access."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.dsn = self._build_dsn()
    
    def _build_dsn(self) -> str:
        """Build PostgreSQL DSN from environment variables."""
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'weather_bot_routing')
        user = os.getenv('POSTGRES_USER', 'postgres')
        password = os.getenv('POSTGRES_PASSWORD', '')
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    async def initialize(self, min_size: int = 5, max_size: int = 20):
        """Initialize connection pool.
        
        Args:
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool
        """
        if self.pool is not None:
            logging.warning("Database pool already initialized")
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=min_size,
                max_size=max_size,
                command_timeout=60,
                ssl='disable'  # Disable SSL for local connections (fixes Windows errors)
            )
            logging.info(f"✅ Graph database pool initialized ({min_size}-{max_size} connections)")
            
            # Verify extensions
            async with self.pool.acquire() as conn:
                postgis_version = await conn.fetchval("SELECT PostGIS_Version();")
                pgrouting_version = await conn.fetchval("SELECT pgr_version();")
                logging.info(f"  PostGIS: {postgis_version}")
                logging.info(f"  pgRouting: {pgrouting_version}")
                
        except Exception as e:
            logging.error(f"❌ Failed to initialize database pool: {e}")
            raise
    
    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logging.info("🔌 Database pool closed")
            self.pool = None
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool.
        
        Usage:
            async with db_manager.acquire() as conn:
                result = await conn.fetch("SELECT * FROM places")
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def health_check(self) -> bool:
        """Check if database is accessible.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            async with self.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            return False
    
    async def get_graph_stats(self) -> dict:
        """Get statistics about the graph database.
        
        Returns:
            Dictionary with places, nodes, edges counts
        """
        try:
            async with self.acquire() as conn:
                stats = await conn.fetchrow("SELECT * FROM graph_stats")
                if stats:
                    return dict(stats)
                return {}
        except Exception as e:
            logging.error(f"Failed to get graph stats: {e}")
            return {}

# Global instance
graph_db = GraphDatabaseManager()
