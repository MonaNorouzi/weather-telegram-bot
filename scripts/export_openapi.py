#!/usr/bin/env python3
"""
Export OpenAPI specification for GPT Custom Actions

This script generates openapi.json that can be imported into OpenAI GPT Custom Actions.
Run after deploying to production to update the server URL.
"""

import json
import sys


def export_openapi():
    """Export OpenAPI schema with GPT-friendly descriptions"""
    
    # Import FastAPI app
    try:
        from api.main import app
    except ImportError as e:
        print(f"❌ Error importing FastAPI app: {e}")
        print("Make sure you're running from project root: python scripts/export_openapi.py")
        sys.exit(1)
    
    # Generate OpenAPI schema
    openapi_schema = app.openapi()
    
    # Customize for GPT
    openapi_schema["info"]["title"] = "Weather Route Planning API"
    openapi_schema["info"]["description"] = (
        "Get detailed weather forecasts for road trips. "
        "This API uses H3-based segment caching to provide fast, accurate weather data "
        "for every segment of your journey. Perfect for trip planning!"
    )
    openapi_schema["info"]["version"] = "1.0.0"
    
    # Add server URL (UPDATE THIS AFTER DEPLOYMENT!)
    openapi_schema["servers"] = [
        {
            "url": "https://weather-gpt-api.onrender.com",
            "description": "Production server (update with your actual URL)"
        },
        {
            "url": "http://localhost:8000",
            "description": "Local development"
        }
    ]
    
    # Save to file
    output_file = "openapi.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    
    print(f"✅ OpenAPI spec exported to {output_file}")
    print(f"📦 Schema contains {len(openapi_schema.get('paths', {}))} endpoints")
    print()
    print("📋 Next steps:")
    print("1. Update the server URL in openapi.json after deployment")
    print("2. Go to https://platform.openai.com/docs/actions")
    print("3. Create a new GPT at https://chat.openai.com/gpts/editor")
    print("4. Add Action → Import from file → Upload openapi.json")
    print()
    print("🧪 Test your API first:")
    print("   curl http://localhost:8000/health")
    

if __name__ == "__main__":
    export_openapi()
