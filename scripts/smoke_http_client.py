import asyncio

from app.utils.enhanced_http import EnhancedHTTPClient

async def main():
    async with EnhancedHTTPClient() as client:
        resp = await client.get("https://httpbin.org/headers")
        print("Status:", resp.status_code)
        print("Headers UA:", resp.request.headers.get("User-Agent"))

if __name__ == "__main__":
    asyncio.run(main())
