-- PostgreSQL Schema for Graph-Based Routing System
-- Implements three-layer architecture: Identity (places) -> Graph (nodes) -> Routing (edges)

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- ============================================================================
-- PLACES TABLE (Identity Layer)
-- ============================================================================
-- Stores unique place entities (cities, villages, POIs)
-- This solves "Name Ambiguity" by treating places as identities separate from road network
CREATE TABLE IF NOT EXISTS places (
    place_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    place_type VARCHAR(50) NOT NULL,  -- city, town, village, hamlet, suburb
    province VARCHAR(100),
    country VARCHAR(100) DEFAULT 'Iran',
    center_geom GEOGRAPHY(POINT, 4326),  -- Center point for display/reference only
    metadata JSONB,  -- Additional OSM tags (population, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_place UNIQUE(name, place_type, province)
);

CREATE INDEX idx_places_name ON places(name);
CREATE INDEX idx_places_type ON places(place_type);
CREATE INDEX idx_places_geom ON places USING GIST(center_geom);

-- ============================================================================
-- NODES TABLE (Graph Layer & Access Points)
-- ============================================================================
-- Stores physical points on the road network
-- Multiple nodes can be linked to a single place (multi-entry access points)
CREATE TABLE IF NOT EXISTS nodes (
    node_id SERIAL PRIMARY KEY,
    geometry GEOGRAPHY(POINT, 4326) NOT NULL,
    linked_place_id INTEGER REFERENCES places(place_id) ON DELETE SET NULL,
    node_label VARCHAR(255),  -- e.g., "Tehran North Entrance"
    node_type VARCHAR(50) DEFAULT 'waypoint',  -- waypoint, access_point, junction
    metadata JSONB,  -- Road type, elevation, etc.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_nodes_geom ON nodes USING GIST(geometry);
CREATE INDEX idx_nodes_place ON nodes(linked_place_id);
CREATE INDEX idx_nodes_type ON nodes(node_type);

-- ============================================================================
-- EDGES TABLE (Routing Layer)
-- ============================================================================
-- Stores road segments connecting nodes
-- Uses deterministic weight calculation: cost = distance / max_speed
CREATE TABLE IF NOT EXISTS edges (
    edge_id SERIAL PRIMARY KEY,
    source_node INTEGER NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    target_node INTEGER NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    geometry GEOGRAPHY(LINESTRING, 4326) NOT NULL,
    distance_meters REAL NOT NULL,
    max_speed_kmh REAL NOT NULL,  -- Inferred from road type or OSRM data
    base_duration_seconds REAL NOT NULL,  -- Deterministic: distance_meters / (max_speed_kmh / 3.6)
    road_type VARCHAR(50),  -- motorway, primary, secondary, residential, etc.
    road_name VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_edge UNIQUE(source_node, target_node),
    CONSTRAINT valid_speed CHECK(max_speed_kmh > 0),
    CONSTRAINT valid_distance CHECK(distance_meters > 0),
    CONSTRAINT valid_duration CHECK(base_duration_seconds > 0)
);

CREATE INDEX idx_edges_source ON edges(source_node);
CREATE INDEX idx_edges_target ON edges(target_node);
CREATE INDEX idx_edges_geom ON edges USING GIST(geometry);
CREATE INDEX idx_edges_road_type ON edges(road_type);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for places table
CREATE TRIGGER update_places_updated_at
BEFORE UPDATE ON places
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate base_duration_seconds from distance and speed
CREATE OR REPLACE FUNCTION calculate_base_duration(
    distance_m REAL,
    speed_kmh REAL
)
RETURNS REAL AS $$
BEGIN
    -- Convert km/h to m/s: speed_kmh / 3.6
    -- duration = distance / (speed / 3.6)
    RETURN distance_m / (speed_kmh / 3.6);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Places with their access node count
CREATE OR REPLACE VIEW places_with_nodes AS
SELECT 
    p.place_id,
    p.name,
    p.place_type,
    p.province,
    COUNT(n.node_id) as access_node_count,
    p.center_geom
FROM places p
LEFT JOIN nodes n ON n.linked_place_id = p.place_id
GROUP BY p.place_id, p.name, p.place_type, p.province, p.center_geom;

-- View: Graph statistics
CREATE OR REPLACE VIEW graph_stats AS
SELECT 
    (SELECT COUNT(*) FROM places) as total_places,
    (SELECT COUNT(*) FROM nodes) as total_nodes,
    (SELECT COUNT(*) FROM edges) as total_edges,
    (SELECT COUNT(*) FROM nodes WHERE linked_place_id IS NOT NULL) as access_nodes,
    (SELECT COUNT(*) FROM nodes WHERE linked_place_id IS NULL) as intermediate_nodes,
    (SELECT SUM(distance_meters) / 1000.0 FROM edges) as total_road_km;

-- ============================================================================
-- SEED DATA (Optional - Major Iranian Cities)
-- ============================================================================

-- Insert major Iranian cities
INSERT INTO places (name, place_type, province, center_geom) VALUES
    ('Tehran', 'city', 'Tehran', ST_SetSRID(ST_MakePoint(51.3890, 35.6892), 4326)),
    ('Isfahan', 'city', 'Isfahan', ST_SetSRID(ST_MakePoint(51.6746, 32.6546), 4326)),
    ('Mashhad', 'city', 'Razavi Khorasan', ST_SetSRID(ST_MakePoint(59.6067, 36.2972), 4326)),
    ('Shiraz', 'city', 'Fars', ST_SetSRID(ST_MakePoint(52.5836, 29.5918), 4326)),
    ('Tabriz', 'city', 'East Azerbaijan', ST_SetSRID(ST_MakePoint(46.2919, 38.0801), 4326)),
    ('Qom', 'city', 'Qom', ST_SetSRID(ST_MakePoint(50.8764, 34.6416), 4326)),
    ('Karaj', 'city', 'Alborz', ST_SetSRID(ST_MakePoint(50.9915, 35.8327), 4326)),
    ('Ahvaz', 'city', 'Khuzestan', ST_SetSRID(ST_MakePoint(48.6693, 31.3183), 4326)),
    ('Kermanshah', 'city', 'Kermanshah', ST_SetSRID(ST_MakePoint(47.0778, 34.3142), 4326)),
    ('Rasht', 'city', 'Gilan', ST_SetSRID(ST_MakePoint(49.5832, 37.2808), 4326))
ON CONFLICT (name, place_type, province) DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE places IS 'Identity layer: unique place entities, separate from road network';
COMMENT ON TABLE nodes IS 'Graph layer: physical points on road network, with optional place linkage';
COMMENT ON TABLE edges IS 'Routing layer: road segments with deterministic weights';
COMMENT ON COLUMN nodes.linked_place_id IS 'Links this node to a place as an access point. Multiple nodes can link to one place.';
COMMENT ON COLUMN edges.base_duration_seconds IS 'Deterministic travel time without traffic or weather. Recalculated as distance_meters / (max_speed_kmh / 3.6)';
