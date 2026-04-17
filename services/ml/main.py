import asyncio

from estategap_ml.trainer.__main__ import main as trainer_main


async def main() -> int:
    return await trainer_main()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
