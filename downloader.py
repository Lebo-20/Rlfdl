import os
import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

async def download_file(client: httpx.AsyncClient, url: str, path: str, progress_callback=None):
    """Downloads a single file with potential progress tracking."""
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            
            total_size = int(response.headers.get("Content-Length", 0))
            download_size = 0
            
            with open(path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
                    download_size += len(chunk)
                    if progress_callback:
                        await progress_callback(download_size, total_size)
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False

from api import get_video_url

async def download_all_episodes(episodes, download_dir: str, semaphore_count: int = 4):
    """
    Downloads all episodes concurrently using a shared client for connection pooling.
    """
    os.makedirs(download_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(semaphore_count)

    async def limited_download(client: httpx.AsyncClient, ep):
        async with semaphore:
            ep_num = str(ep.get('chapterId', 'unk')).zfill(3)
            filename = f"episode_{ep_num}.mp4"
            filepath = os.path.join(download_dir, filename)
            
            book_id = ep.get('bookId')
            chapter_id = ep.get('chapterId')
            if not book_id or not chapter_id:
                logger.error(f"No Book ID or Chapter ID found for episode {ep_num}")
                return False
                
            max_retries = 5 # Increased retries
            for attempt in range(max_retries):
                try:
                    # Fetch URL via API
                    url = await get_video_url(book_id, chapter_id)
                    if not url:
                        logger.error(f"Waiting for URL for {book_id}/{chapter_id} (Attempt {attempt+1})")
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                        
                    success = await download_file(client, url, filepath)
                    if success:
                        # Verify file exists and has minimum size to be a valid video
                        if os.path.exists(filepath):
                            size = os.path.getsize(filepath)
                            if size > 102400: # 100KB minimum
                                logger.info(f"✅ Success Download: {filename} ({size/1024/1024:.2f}MB)")
                                return True
                            else:
                                logger.warning(f"⚠️ Episode {ep_num} is too small ({size} bytes). Retrying...")
                    
                except Exception as e:
                    logger.error(f"Error downloading episode {ep_num} (Attempt {attempt+1}): {e}")
                
                # Backoff before retry
                wait_time = 5 * (attempt + 1)
                await asyncio.sleep(wait_time)
            
            logger.error(f"❌ Giving up on Episode {ep_num} after {max_retries} attempts.")
            return False

    # Use a persistent client session for all downloads
    async with httpx.AsyncClient(timeout=120, limits=httpx.Limits(max_connections=semaphore_count)) as client:
        results = await asyncio.gather(*(limited_download(client, ep) for ep in episodes))
        return all(results)
