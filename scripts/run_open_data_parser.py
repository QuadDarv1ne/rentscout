import asyncio

from app.parsers.open_data_parser import OpenDataParser

async def main():
    parser = OpenDataParser()
    results = await parser.parse(location="Москва", params={})
    print(f"Fetched {len(results)} open-data listings")
    for r in results[:5]:
        print(f"- {r.title} | {r.source} | {r.url}")

if __name__ == "__main__":
    asyncio.run(main())
