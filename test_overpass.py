import asyncio
import aiohttp

async def test_overpass():
    url = 'https://overpass-api.de/api/interpreter'
    query = '''
    [out:json][timeout:30];
    (
        node["place"](around:5000,35.6892,51.3896);
    );
    out body;
    '''
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url, data={'data': query}) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f'Found {len(data.get("elements", []))} places near Tehran')
                for el in data.get('elements', [])[:10]:
                    print(f"  - {el.get('tags', {}).get('name', 'no name')} ({el.get('tags', {}).get('place', 'unknown')})")
            else:
                print(f'Error: {resp.status}')

asyncio.run(test_overpass())
