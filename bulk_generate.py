import asyncio
from main import main

TOTAL_VIDEOS = 5

async def bulk_generate():
    for i in range(TOTAL_VIDEOS):
        print(f"\nCreating video {i + 1} of {TOTAL_VIDEOS}...\n")
        await main()

    print("\nBulk generation completed.")

asyncio.run(bulk_generate())