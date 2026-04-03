import os
import asyncio
import httpx
import tempfile
import subprocess
import logging
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeVideo

logger = logging.getLogger(__name__)

async def upload_progress(current, total, event, msg_text="Uploading..."):
    """Callback function for upload progress."""
    percentage = (current / total) * 100
    try:
        # Avoid flood by updating every few percentages
        if int(percentage) % 10 == 0:
            await event.edit(f"{msg_text} {percentage:.1f}%")
    except:
        pass

async def upload_drama(client: TelegramClient, chat_id: int, 
                       title: str, description: str, 
                       poster_url: str, video_path: str):
    """
    Uploads the drama information and merged video to Telegram.
    Refactored to ensure title consistency.
    """
    try:
        # 1. FINAL CONSISTENCY CHECK
        # Jika judul masih berupa ID default, ambil dari nama file video (video_path)
        filename_title = os.path.splitext(os.path.basename(video_path))[0]
        # Clean title from ID fallback if filename is better
        if title.startswith("Drama_") or not title or title == "Unknown":
            if filename_title and not filename_title.startswith("Drama_") and filename_title != "Unknown":
                title = filename_title
                logger.info(f"🔄 Judul diselaraskan dengan nama file: {title}")

        # Bersihkan deskripsi
        if not description or "No description" in description:
            description = "Sinopsis belum tersedia untuk drama ini."

        # 2. Persiapkan Caption (Gunakan format Bold/Premium)
        caption = (
            f"🎬 **{title.upper()}**\n\n"
            f"📝 **Sinopsis:**\n"
            f"_{description[:800] if description else 'No description available.'}_\n\n"
            f"✅ **Kualitas:** Full HD 720p\n"
            f"📌 **Status:** Full Episode"
        )
        
        # 3. Handle Poster
        poster_path = None
        if poster_url and poster_url.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=30) as http_client:
                    resp = await http_client.get(poster_url)
                    if resp.status_code == 200:
                        poster_path = os.path.join(tempfile.gettempdir(), f"poster_{hash(title)}.jpg")
                        with open(poster_path, "wb") as pf:
                            pf.write(resp.content)
            except Exception as e:
                logger.warning(f"Gagal download poster: {e}")

        # Kirim Poster dengan Caption Detail
        if poster_path:
            await client.send_file(chat_id, poster_path, caption=caption, parse_mode='md')
            if os.path.exists(poster_path):
                os.remove(poster_path)
        else:
            await client.send_message(chat_id, caption, parse_mode='md')
        
        status_msg = await client.send_message(chat_id, "📤 **Sedang memproses video...**")
        
        # 4. Extract Video Metadata (Duration & Thumb)
        duration = 0
        width, height = 0, 0
        try:
            ffprobe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            output = subprocess.check_output(ffprobe_cmd, text=True).strip().split('\n')
            if len(output) >= 3:
                width, height = int(output[0]), int(output[1])
                duration = int(float(output[2]))
        except Exception as e:
            logger.warning(f"Failed to extract video info: {e}")

        thumb_path = os.path.join(tempfile.gettempdir(), f"thumb_{hash(title)}.jpg")
        try:
            subprocess.run(["ffmpeg", "-y", "-i", video_path, "-ss", "00:00:02", "-vframes", "1", thumb_path], capture_output=True)
            if not os.path.exists(thumb_path):
                thumb_path = None
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {e}")
            thumb_path = None

        # 5. Final Upload (Video Streamable)
        from telethon.tl.types import DocumentAttributeVideo
        video_attributes = [
            DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True)
        ]
        
        await client.send_file(
            chat_id,
            video_path,
            caption=f"🎥 **VIDEO FULL:** {title}\n📌 Jangan lupa Subscribe!",
            force_document=False, # FORCE IT AS VIDEO STREAM
            thumb=thumb_path,
            attributes=video_attributes,
            progress_callback=lambda c, t: upload_progress(c, t, status_msg, "🚀 Uploading Video:"),
            supports_streaming=True
        )
        
        await status_msg.delete()
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
            
        logger.info(f"✅ Sukses upload sesuai judul: {title}")
        return True

    except Exception as e:
        logger.error(f"❌ Gagal upload: {e}")
        return False
