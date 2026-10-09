
import os
import asyncio
from telethon import TelegramClient

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]

async def main():
    async with TelegramClient("telegram_migration", API_ID, API_HASH) as client:
        async for dialog in client.iter_dialogs():
            if dialog.is_channel:
                print(
                    f"Name: {dialog.name} | "
                    f"ID: {dialog.entity.id} | "
                    f"Access hash: {getattr(dialog.entity, 'access_hash', None)}"
                )

asyncio.run(main())

