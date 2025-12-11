import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector

async def test_photon_with_proxy():
    url = "https://photon.komoot.io/reverse"
    params = {"lat": 35.6892, "lon": 51.3896}
    proxy_url = "socks5://127.0.0.1:10808"
    
    print("Testing Photon API with SOCKS5 proxy...")
    
    try:
        connector = ProxyConnector.from_url(proxy_url)
        async with aiohttp.ClientSession(connector=connector) as sess:
            async with sess.get(url, params=params) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    features = data.get("features", [])
                    if features:
                        name = features[0].get("properties", {}).get("name", "Unknown")
                        print(f"✅ Found: {name}")
                    else:
                        print("No features in response")
                else:
                    print(f"Error: {await resp.text()}")
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test_photon_with_proxy())
