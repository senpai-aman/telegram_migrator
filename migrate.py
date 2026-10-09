
import asyncio
import os
import sqlite3
import sys

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SOURCE = os.environ["TG_SOURCE"]
DESTINATION = os.environ["TG_DEST"]

SESSION = "telegram_migration"
DB_FILE = "migration.sqlite3"

# First run: test only 10 source messages.
# Set TG_MAX_POSTS=0 for the full migration.
MAX_POSTS = int(os.environ.get("TG_MAX_POSTS", "10"))


def open_db():
    db = sqlite3.connect(DB_FILE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            name TEXT PRIMARY KEY,
            message_id INTEGER NOT NULL
        )
    """)
    db.execute("""
        INSERT OR IGNORE INTO progress(name, message_id)
        VALUES ('last_id', 0)
    """)
    db.commit()
    return db


def last_id(db):
    return db.execute(
        "SELECT message_id FROM progress WHERE name='last_id'"
    ).fetchone()[0]


def save_progress(db, message_id):
    db.execute(
        "UPDATE progress SET message_id=? WHERE name='last_id'",
        (message_id,),
    )
    db.commit()


async def forward_with_retry(client, destination, source, messages):
    """Forward existing Telegram messages without author attribution."""
    while True:
        try:
            await client.forward_messages(
                destination,
                messages,
                from_peer=source,
                drop_author=True,
                drop_media_captions=False,
                silent=True,
            )
            await asyncio.sleep(1)
            return
        except FloodWaitError as exc:
            delay = exc.seconds + 1
            print(f"Rate limited. Waiting {delay} seconds...")
            await asyncio.sleep(delay)


async def main():
    db = open_db()
    client = TelegramClient(SESSION, API_ID, API_HASH)

    try:
        await client.start()

        dialogs = await client.get_dialogs()

        source_id = int(SOURCE)
        destination_id = int(DESTINATION)

        source = next(
            (
                d.entity for d in dialogs
                if d.is_channel and d.entity.id == source_id
            ),
            None,
        )

        destination = next(
            (
                d.entity for d in dialogs
                if d.is_channel and d.entity.id == destination_id
            ),
            None,
        )

        if source is None:
            raise RuntimeError(f"Source channel {source_id} not found")

        if destination is None:
            raise RuntimeError(
                f"Destination channel {destination_id} not found"
            )

        checkpoint = last_id(db)

        print(f"Source: {source.title} (ID: {source.id})")
        print(f"Destination: {destination.title} (ID: {destination.id})")
        print(f"Resume after message ID: {checkpoint}")
        print(f"Maximum messages: {MAX_POSTS or 'unlimited'}")
        print("Starting streaming migration...", flush=True)

        processed = 0
        pending_album = []
        pending_group_id = None


        async def copy_group(group):
            nonlocal processed

            if not group:
                return True

            if MAX_POSTS and processed >= MAX_POSTS:
                print("Test limit reached.")
                return False

            # First, try forwarding the message or entire album.
            try:
                await forward_with_retry(
                    client, destination, source, group
                )

                processed += len(group)
                save_progress(db, group[-1].id)

                print(
                    f"Copied through source ID {group[-1].id}; "
                    f"processed {processed} messages",
                    flush=True,
                )
                return True

            except RPCError as exc:
                # If an album fails, retry its members individually.
                # This allows accessible media to be copied even if
                # one member of the album is restricted.
                if len(group) > 1:
                    print(
                        f"Album ending at ID {group[-1].id} failed: "
                        f"{exc}. Retrying members individually.",
                        flush=True,
                    )

                    for item in group:
                        try:
                            await forward_with_retry(
                                client, destination, source, item
                            )

                            processed += 1
                            print(
                                f"Copied source ID {item.id}",
                                flush=True,
                            )

                        except RPCError as item_exc:
                            error_name = type(item_exc).__name__
                            error_text = str(item_exc).lower()

                            skippable = (
                                error_name in {
                                    "MessageIdInvalidError",
                                    "MediaEmptyError",
                                    "ChatForwardsRestrictedError",
                                }
                                or "specified message id is invalid"
                                in error_text
                                or "restricted" in error_text
                                or "can't do that operation on such message"
                                in error_text
                            )

                            if not skippable:
                                raise

                            print(
                                f"SKIPPED source ID {item.id}: "
                                f"{item_exc}",
                                flush=True,
                            )

                        # Advance even for a skipped member, so the
                        # migration won't get stuck on it again.
                        save_progress(db, item.id)

                    return True

                # A single message failed. Skip only known message-
                # specific restrictions; stop for other errors.
                error_name = type(exc).__name__
                error_text = str(exc).lower()

                skippable = (
                    error_name in {
                        "MessageIdInvalidError",
                        "MediaEmptyError",
                        "ChatForwardsRestrictedError",
                    }
                    or "specified message id is invalid"
                    in error_text
                    or "restricted" in error_text
                    or "can't do that operation on such message"
                    in error_text
                )

                if not skippable:
                    raise

                print(
                    f"SKIPPED source ID {group[0].id}: {exc}",
                    flush=True,
                )
                save_progress(db, group[0].id)
                return True


        async def flush_album():
            nonlocal pending_album, pending_group_id

            if not pending_album:
                return True

            group = pending_album
            pending_album = []
            pending_group_id = None

            return await copy_group(group)

        async for msg in client.iter_messages(
            source, reverse=True, min_id=checkpoint
        ):
            # Flush any pending album before handling a service event.
            if msg.action is not None:
                if not await flush_album():
                    break

                save_progress(db, msg.id)
                continue

            # Keep consecutive album messages together.
            if msg.grouped_id is not None:
                if (
                    pending_album
                    and msg.grouped_id != pending_group_id
                ):
                    if not await flush_album():
                        break

                if not pending_album:
                    pending_group_id = msg.grouped_id

                pending_album.append(msg)
                continue

            # A normal message marks the end of any preceding album.
            if not await flush_album():
                break

            if MAX_POSTS and processed >= MAX_POSTS:
                print("Test limit reached.")
                break

            if not await copy_group([msg]):
                break

        else:
            # The iterator finished normally: flush the final album.
            await flush_album()

        print("Migration run finished.")
        print(f"Messages copied this run: {processed}")
        print(f"Last saved source ID: {last_id(db)}")

    finally:
        db.close()
        await client.disconnect()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user. Rerun to resume.")
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)

