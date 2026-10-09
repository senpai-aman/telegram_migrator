# Telegram Migrator

A Python-based Telegram channel migration tool built with [Telethon](https://github.com/LonamiWebs/Telethon). It bulk-copies messages between Telegram channels without the original forward attribution, while keeping media hosted on Telegram.

## Features

- **Bulk migration:** Copy existing channel messages in chronological order.
- **No media re-upload:** Uses Telegram's forwarding API to avoid downloading and uploading media through your computer.
- **Remove forward attribution:** Copies messages without the original forward-author attribution.
- **Media and albums:** Supports photos, videos, documents, text messages, captions, and grouped media albums where Telegram permits forwarding.
- **Private channels:** Supports channels accessible to your Telegram account using numeric channel IDs.
- **Resume support:** Saves migration progress in an SQLite database.
- **Flood-wait handling:** Waits when Telegram applies rate limits.
- **Restricted-message handling:** Skips certain messages that Telegram refuses to forward and continues with subsequent posts.
- **Configurable message limit:** Test with a limited number of messages or migrate the remaining history.

## Requirements

- Python 3.9 or newer
- A Telegram account with access to the source channel
- Permission to post in the destination channel
- Telegram API credentials (`api_id` and `api_hash`)
- Fedora Linux or another Linux distribution with Python and `venv` support

## Repository Structure

```text
telegram_migrator/
├── env                 # Example environment configuration
├── LICENSE             # Project license
├── list_channels.py    # Lists accessible Telegram channels and IDs
├── migrate.py          # Main migration script
└── README.md           # Project documentation
```

Runtime files are generated when you run the scripts. These include the Python virtual environment, Telethon session, and SQLite migration checkpoint.

## 1. Clone the Repository

```bash
git clone https://github.com/senpai-aman/telegram_migrator.git
cd telegram_migrator
```

## 2. Create a Python Virtual Environment

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip and install the required dependency:

```bash
python -m pip install --upgrade pip
python -m pip install "telethon>=1.40,<2"
```

Whenever you open a new terminal, activate the environment again:

```bash
cd telegram_migrator
source .venv/bin/activate
```

## 3. Obtain Telegram API Credentials

1. Visit [my.telegram.org](https://my.telegram.org).
2. Sign in using your Telegram phone number.
3. Open **API development tools**.
4. Create an application if prompted.
5. Copy your `api_id` and `api_hash`.

Keep these credentials private. Never publish your actual API hash or authenticated Telegram session.

## 4. Configure the Environment

The repository includes an `env` file with example values:

```bash
# Update the configuration as mentioned in README
export TG_API_ID="YOUR_API_ID"
export TG_API_HASH="YOUR_API_HASH"

# Numeric Telegram channel IDs
export TG_SOURCE="@src_channel_num_id"
export TG_DEST="@dest_channel_num_id"

# 0 = unlimited messages
export TG_MAX_POSTS=0
```

Edit the file:

```bash
nano env
```

Update the values as follows:

- `TG_API_ID`: Your Telegram API application ID.
- `TG_API_HASH`: Your Telegram API application hash.
- `TG_SOURCE`: Numeric ID of the source channel.
- `TG_DEST`: Numeric ID of the destination channel.
- `TG_MAX_POSTS`: Maximum number of messages to copy; `0` disables the configured count limit.

**Important:** Replace the example channel values with numeric IDs, without the `@` symbol. For example:

```bash
export TG_SOURCE="3979345032"
export TG_DEST="3885609475"
```

Load the environment variables into your current shell:

```bash
source env
```

Verify the non-secret configuration:

```bash
echo "$TG_SOURCE"
echo "$TG_DEST"
echo "$TG_MAX_POSTS"
```

## 5. Find Channel IDs

Use `list_channels.py` to list the channels accessible to your Telegram account:

```bash
source env
python list_channels.py
```

On the first run, Telethon may ask you to authenticate using your phone number, Telegram login code, and two-step verification password if enabled.

Example output:

```text
Name: New channel | ID: 3885609475 | Access hash: ...
Name: Old channel | ID: 3979345032 | Access hash: ...
```

Copy the numeric IDs into `TG_SOURCE` and `TG_DEST` in your `env` file.

Both channels must be accessible to your account. The destination must allow your account to post messages.

## 6. Run a Test Migration

Before migrating the entire history, start with a small test:

```bash
source .venv/bin/activate
source env

export TG_MAX_POSTS=10
python -u migrate.py
```

The first run may ask you to authenticate with Telegram. Follow the prompts in your terminal.

Verify that the destination channel contains the expected messages and media.

Check the following:

- Messages appear in chronological order.
- Forward attribution has been removed.
- Captions and text are preserved where supported.
- Albums remain grouped where Telegram supports it.
- Restricted messages are logged as skipped when applicable.

## 7. Migrate All Remaining Messages

After verifying the test, set the message limit to zero:

```bash
source .venv/bin/activate
source env

export TG_MAX_POSTS=0
python -u migrate.py
```

The script will process the source history after the saved checkpoint.

**Important:** Zero means no configured message-count limit. Telegram API rate limits still apply, and some messages may be skipped if Telegram refuses to forward them.

## 8. Resume an Interrupted Migration

The script stores its progress in:

```text
migration.sqlite3
```

It also uses a Telethon session file, typically:

```text
telegram_migration.session
```

To resume, activate the environment, load the same configuration, and run:

```bash
source .venv/bin/activate
source env

export TG_MAX_POSTS=0
python -u migrate.py
```

Keep the same database and session files. Do not delete or replace them while you intend to resume the same migration.

The checkpoint records the last saved source message ID. If Telegram accepts a message but the program stops before saving progress, a duplicate may occur on retry.

## 9. Rate Limits

Telegram does not publish a universal forwarding rate limit that guarantees a fixed number of messages per minute.

The script handles `FloodWaitError` by waiting for the duration returned by Telegram before retrying the request.

For large migrations:

- Allow the script to wait when Telegram imposes a flood wait.
- Do not repeatedly restart the script to bypass rate limits.
- Avoid running concurrent migration sessions on the same account.
- Keep a stable internet connection.
- Expect migration time to vary based on history size, albums, network latency, and rate limits.

## 10. Restricted Messages and Errors

Some messages may be unavailable for forwarding because of Telegram restrictions, invalid message references, or other server-side limitations.

The script can skip recognized message-specific forwarding errors and continue with subsequent posts. When an album fails, its members may be retried individually, which can split the album.

Unexpected errors stop the migration rather than being silently ignored.

This tool does not bypass Telegram's content protection or forwarding restrictions.


## Disclaimer

This project is an independent community tool and is not affiliated with Telegram.

Use it only for content you own or have permission to copy. Follow Telegram's terms, applicable laws, and the source channel's content restrictions. The author is not responsible for misuse of the software.

## License

See [LICENSE](LICENSE) for the license terms.