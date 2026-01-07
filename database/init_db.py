#!/usr/bin/env python3
"""Database initialization script for Graph Routing System.

This script:
1. Creates the database if it doesn't exist
2. Enables PostGIS and pgRouting extensions
3. Executes schema.sql to create tables and indices
4. Verifies the setup is correct
"""
from dotenv import load_dotenv
load_dotenv()  
import os
import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Database configuration (can be overridden by environment variables)
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'weather_bot_routing'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', ''),
}

async def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    # Connect to default 'postgres' database to create our database
    conn = await asyncpg.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database='postgres'
    )
    
    try:
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            DB_CONFIG['database']
        )
        
        if not exists:
            print(f"📦 Creating database '{DB_CONFIG['database']}'...")
            await conn.execute(f"CREATE DATABASE {DB_CONFIG['database']}")
            print(f"✅ Database '{DB_CONFIG['database']}' created successfully")
        else:
            print(f"✅ Database '{DB_CONFIG['database']}' already exists")
    finally:
        await conn.close()

async def initialize_schema():
    """Initialize schema by executing schema.sql."""
    conn = await asyncpg.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database']
    )
    
    try:
        # Read schema.sql
        schema_path = Path(__file__).parent / 'schema.sql'
        if not schema_path.exists():
            raise FileNotFoundError(f"schema.sql not found at {schema_path}")
        
        print(f"📄 Reading schema from {schema_path}")
        schema_sql = schema_path.read_text(encoding='utf-8')
        
        # Execute schema
        print("🔨 Executing schema...")
        await conn.execute(schema_sql)
        print("✅ Schema executed successfully")
        
        # Verify extensions
        print("\n🔍 Verifying extensions...")
        postgis_version = await conn.fetchval("SELECT PostGIS_Version();")
        print(f"  ✅ PostGIS installed: {postgis_version}")
        
        pgrouting_version = await conn.fetchval("SELECT pgr_version();")
        print(f"  ✅ pgRouting installed: {pgrouting_version}")
        
        # Verify tables
        print("\n🔍 Verifying tables...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        expected_tables = {'places', 'nodes', 'edges'}
        found_tables = {row['table_name'] for row in tables}
        
        for table in expected_tables:
            if table in found_tables:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"  ✅ Table '{table}' exists ({count} rows)")
            else:
                print(f"  ❌ Table '{table}' NOT FOUND")
        
        # Show graph stats
        print("\n📊 Graph Statistics:")
        stats = await conn.fetchrow("SELECT * FROM graph_stats")
        if stats:
            print(f"  Places: {stats['total_places']}")
            print(f"  Nodes: {stats['total_nodes']} (Access: {stats['access_nodes']}, Intermediate: {stats['intermediate_nodes']})")
            print(f"  Edges: {stats['total_edges']}")
            print(f"  Total Road Distance: {stats['total_road_km']:.2f} km" if stats['total_road_km'] else "  Total Road Distance: 0 km")
        
    finally:
        await conn.close()

async def main():
    """Main initialization function."""
    print("=" * 60)
    print("Graph Database Initialization")
    print("=" * 60)
    print(f"\n🔌 Connection: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    try:
        # Step 1: Create database
        await create_database_if_not_exists()
        
        # Step 2: Initialize schema
        await initialize_schema()
        
        print("\n" + "=" * 60)
        print("✅ Database initialization completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
