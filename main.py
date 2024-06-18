import asyncio
import os
import time
from uuid import uuid4

import redis
import telethon
import telethon.tl.types
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ForwardMessagesRequest
from telethon.types import Message, UpdateNewMessage
from aiohttp import web

from cansend import CanSend
from config import *
from terabox import get_data
from tools import (
    convert_seconds,
    download_file,
    download_image_to_bytesio,
    extract_code_from_url,
    get_formatted_size,
    get_urls_from_string,
    is_user_on_chat,
)

# Initialize Telegram bot
bot = TelegramClient("tele", API_ID, API_HASH)

# Configure Redis
db = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

@bot.on(
    events.NewMessage(
        pattern="/start$",
        incoming=True,
        outgoing=False,
        func=lambda x: x.is_private,
    )
)
async def start(event: UpdateNewMessage):
    reply_text = f"""
Hello! I am a bot to download videos from terabox.
Send me the terabox link and I will start downloading it.
Join @RoldexVerse For Updates
[Source Code](https://github.com/r0ld3x/terabox-downloader-bot) """
    check_if = await is_user_on_chat(bot, "@SK_MoviesOffl", event.peer_id)
    if not check_if:
        return await event.reply("Please join @SK_MoviesOffl then send me the link again.")
    check_if = await is_user_on_chat(bot, "@SK_MoviesOffl", event.peer_id)
    if not check_if:
        return await event.reply(
            "Please join @SK_MoviesOffl then send me the link again."
        )
    await event.reply(reply_text, link_preview=False, parse_mode="markdown")

@bot.on(
    events.NewMessage(
        pattern="/start (.*)",
        incoming=True,
        outgoing=False,
        func=lambda x: x.is_private,
    )
)
async def start(event: UpdateNewMessage):
    text = event.pattern_match.group(1)
    fileid = db.get(str(text))
    check_if = await is_user_on_chat(bot, "@SK_MoviesOffl", event.peer_id)
    if not check_if:
        return await event.reply("Please join @SK_MoviesOffl then send me the link again.")
    check_if = await is_user_on_chat(bot, "@SK_MoviesOffl", event.peer_id)
    if not check_if:
        return await event.reply(
            "Please join @SK_MoviesOffl then send me the link again."
        )
    await bot(
        ForwardMessagesRequest(
            from_peer=PRIVATE_CHAT_ID,
            id=[int(fileid)],
            to_peer=event.chat_id,
            drop_author=True,
            background=True,
            drop_media_captions=False,
            with_my_score=True,
        )
    )

@bot.on(
    events.NewMessage(
        pattern="/remove (.*)",
        incoming=True,
        outgoing=False,
        from_users=ADMINS,
    )
)
async def remove(event: UpdateNewMessage):
    user_id = event.pattern_match.group(1)
    if db.get(f"check_{user_id}"):
        db.delete(f"check_{user_id}")
        await event.reply(f"Removed {user_id} from the list.")
    else:
        await event.reply(f"{user_id} is not in the list.")

@bot.on(
    events.NewMessage(
        incoming=True,
        outgoing=False,
        func=lambda message: message.text
        and get_urls_from_string(message.text)
        and message.is_private,
    )
)
async def get_message(event: Message):
    asyncio.create_task(handle_message(event))

async def handle_message(event: Message):
    url = get_urls_from_string(event.text)
    if not url:
        return await event.reply("Please enter a valid url.")
    check_if = await is_user_on_chat(bot, "@SK_MoviesOffl", event.peer_id)
    if not check_if:
        return await event.reply("Please join @RoldexVerse then send me the link again.")
    check_if = await is_user_on_chat(bot, "@SK_MoviesOffl", event.peer_id)
    if not check_if:
        return await event.reply(
            "Please join @SK_MoviesOffl then send me the link again."
        )
    is_spam = db.get(event.sender_id)
    if is_spam and event.sender_id not in [1317173146]:
        return await event.reply("You are spamming. Please wait a 1 minute and try again.")
    hm = await event.reply("Sending you the media wait...")
    count = db.get(f"check_{event.sender_id}")
    if count and int(count) > 5:
        return await hm.edit(
            "You are limited now. Please come back after 2 hours or use another account."
        )
    shorturl = extract_code_from_url(url)
    if not shorturl:
        return await hm.edit("Seems like your link is invalid.")
    fileid = db.get(shorturl)
    if fileid:
        try:
            await hm.delete()
        except:
            pass

        await bot(
            ForwardMessagesRequest(
                from_peer=PRIVATE_CHAT_ID,
                id=[int(fileid)],
                to_peer=event.chat_id,
                drop_author=True,
                background=True,
                drop_media_captions=False,
                with_my_score=True,
            )
        )
        db.set(event.sender_id, time.monotonic(), ex=60)
        db.set(
            f"check_{event.sender_id}",
            int(count) + 1 if count else 1,
            ex=7200,
        )

        return

    data = get_data(url)
    if not data:
        return await hm.edit("Sorry! API is dead or maybe your link is broken.")
    db.set(event.sender_id, time.monotonic(), ex=60)
    if (
        not data["file_name"].endswith(".mp4")
        and not data["file_name"].endswith(".mkv")
        and not data["file_name"].endswith(".Mkv")
        and not data["file_name"].endswith(".webm")
    ):
        return await hm.edit(
            f"Sorry! File is not supported for now. I can download only .mp4, .mkv and .webm files."
        )
    if int(data["sizebytes"]) > 524288000 and event.sender_id not in [1317173146]:
        return await hm.edit(
            f"Sorry! File is too big. I can download only 500MB and this file is of {data['size']} ."
        )

    start_time = time.time()
    cansend = CanSend()

    async def progress_bar(current_downloaded, total_downloaded, state="Sending"):
        if not cansend.can_send():
            return
        bar_length = 20
        percent = current_downloaded / total_downloaded
        arrow = "█" * int(percent * bar_length)
        spaces = "░" * (bar_length - len(arrow))

        elapsed_time = time.time() - start_time

        head_text = f"{state} `{data['file_name']}`"
        progress_bar = f"[{arrow + spaces}] {percent:.2%}"
        upload_speed = current_downloaded / elapsed_time if elapsed_time > 0 else 0
        speed_line = f"Speed: **{get_formatted_size(upload_speed)}/s**"

        time_remaining = (
            (total_downloaded - current_downloaded) / upload_speed
            if upload_speed > 0
            else 0
        )
        time_line = f"Time Remaining: `{convert_seconds(time_remaining)}`"

        size_line = f"Size: **{get_formatted_size(current_downloaded)}** / **{get_formatted_size(total_downloaded)}**"

        await hm.edit(
            f"{head_text}\n{progress_bar}\n{speed_line}\n{time_line}\n{size_line}",
            parse_mode="markdown",
        )

    uuid = str(uuid4())
    thumbnail = download_image_to_bytesio(data["thumb"], "thumbnail.png")

    try:
        file = await bot.send_file(
            PRIVATE_CHAT_ID,
            file=data["direct_link"],
            thumb=thumbnail if thumbnail else None,
            progress_callback=progress_bar,
            caption=f"""
File Name: `{data['file_name']}`
Size: **{data["size"]}** 
Direct Link: [Click Here](https://t.me/Links_Bypasss_bot?start={uuid})

@SK_MoviesOffl
""",
            supports_streaming=True,
            spoiler=True,
        )

        # pm2 start python3 --name "terabox" -- main.py
    except telethon.errors.rpcerrorlist.WebpageCurlFailedError:
        download = await download_file(
            data["direct_link"], data["file_name"], progress_bar
        )
        if not download:
            return await hm.edit(
                f"Sorry! Download Failed but you can download it from [here]({data['direct_link']}).",
                parse_mode="markdown",
            )
        file = await bot.send_file(
            PRIVATE_CHAT_ID,
            download,
            caption=f"""
File Name: `{data['file_name']}`
Size: **{data["size"]}** 
Direct Link: [Click Here](https://t.me/Links_Bypasss_bot?start={uuid})

@SK_MoviesOffl
""",
            progress_callback=progress_bar,
            thumb=thumbnail if thumbnail else None,
            supports_streaming=True,
            spoiler=True,
        )
        try:
            os.unlink(download)
        except Exception as e:
            print(e)
    except Exception:
        return await hm.edit(
            f"Sorry! Download Failed but you can download it from [here]({data['direct_link']}).",
            parse_mode="markdown",
        )
    try:
        os.unlink(download)
    except Exception as e:
        pass
    try:
        await hm.delete()
    except Exception as e:
        print(e)

    if shorturl:
        db.set(shorturl, file.id)
    if file:
        db.set(uuid, file.id)

        await bot(
            ForwardMessagesRequest(
                from_peer=PRIVATE_CHAT_ID,
                id=[file.id],
                to_peer=event.chat_id,
                top_msg_id=event.id,
                drop_author=True,
                background=True,
                drop_media_captions=False,
                with_my_score=True,
            )
        )
        db.set(event.sender_id, time.monotonic(), ex=60)
        db.set(
            f"check_{event.sender_id}",
            int(count) + 1 if count else 1,
            ex=7200,
        )


# Aiohttp server for health check
async def handle(request):
    return web.Response(text="Bot is running")


app = web.Application()
app.add_routes([web.get("/", handle)])

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Start the bot
    loop.run_until_complete(bot.start(bot_token=BOT_TOKEN))
    print("Bot is running...")

    # Run the web server
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8000)))
    loop.run_until_complete(site.start())

    # Keep the loop running
    loop.run_forever()

