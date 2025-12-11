import asyncio
import aiohttp

async def test_nominatim():
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": 35.6892, "lon": 51.3896, "format": "json", "addressdetails": 1}
    headers = {"User-Agent": "WeatherBot/1.0"}
    
    print("Testing Nominatim...")
    
    try:
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.get(url, params=params) as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"Name: {data.get('name', 'N/A')}")
                    print(f"Address: {data.get('address', {})}")
                else:
                    print(f"Error: {await resp.text()}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_nominatim())
