import asyncio

from estategap_ml.__main__ import main as package_main


async def main() -> int:
    return await package_main()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
