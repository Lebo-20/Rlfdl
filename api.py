import httpx
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://reelife.dramabos.my.id/api/v1"
AUTH_CODE = "A8D6AB170F7B89F2182561D3B32F390D"

async def get_latest_dramas(pages=1, page_start=1, lang="in"):
    """Fetches latest dramas from ReeLife API home section."""
    all_dramas = []
    
    async with httpx.AsyncClient(timeout=30) as client:
        for p in range(page_start, page_start + pages):
            url = f"{BASE_URL}/home"
            params = {
                "lang": lang,
                "page": p
            }
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    # Support both Reelife (data['dramas']) and common structures
                    dramas = data.get("dramas") or data.get("data", []) if not isinstance(data.get("data"), dict) else data.get("data", {}).get("dramas", [])
                    if not dramas and isinstance(data.get("data"), list):
                        dramas = data.get("data")
                    
                    if not dramas:
                        break
                    all_dramas.extend(dramas)
                    if not data.get("hasMore", False):
                        break
                else:
                    break
            except Exception as e:
                logger.error(f"Error fetching home page {p}: {e}")
                break
    
    return all_dramas

# Compatibility alias
async def get_latest_idramas(pages=1):
    return await get_latest_dramas(pages=pages)

async def get_drama_detail(book_id: str, lang="in"):
    """Fetches drama detail from ReeLife API."""
    url = f"{BASE_URL}/book/{book_id}"
    params = {"lang": lang}
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
                
            # Root level success check
            if data.get("code") == 0 or "data" in data or "bookVo" in data:
                # Logic to find the main drama object (often called bookVo)
                inner_data = data.get("data") or data
                
                # If it's a dict containing bookVo, dive in
                if isinstance(inner_data, dict):
                    if "bookVo" in inner_data:
                        return inner_data["bookVo"]
                    # Fallback: if data itself has the fields
                    if "bookName" in inner_data or "title" in inner_data or "name" in inner_data:
                        return inner_data
                
                # Fallback: check root if it has the fields
                if "bookName" in data or "title" in data:
                    return data
            
            return None
        except Exception as e:
            logger.error(f"Error fetching drama detail for {book_id}: {e}")
            return None

# Compatibility alias
async def get_idrama_detail(book_id: str):
    return await get_drama_detail(book_id)

async def get_all_episodes(book_id: str, lang="in"):
    """Fetches episodes list (chapters) from ReeLife API."""
    url = f"{BASE_URL}/book/{book_id}/chapters"
    params = {"lang": lang}
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and (data.get("code") == 0 or "data" in data):
                # Based on observation, chapters are in data['data']['chapterList'] 
                # or just data['list'] or data['episodes']
                inner_data = data.get("data") or data
                if isinstance(inner_data, dict):
                    return inner_data.get("chapterList") or inner_data.get("list") or inner_data.get("episodes") or []
                elif isinstance(inner_data, list):
                    return inner_data
            return []
        except Exception as e:
            logger.error(f"Error fetching episodes for {book_id}: {e}")
            return []

# Compatibility alias
async def get_idrama_all_episodes(book_id: str):
    return await get_all_episodes(book_id)

async def search_dramas(query: str, page=1, lang="in"):
    """Searches dramas by title."""
    url = f"{BASE_URL}/search"
    params = {
        "lang": lang,
        "q": query,
        "page": page
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and (data.get("code") == 0 or "dramas" in data or "data" in data):
                inner_data = data.get("data") or data
                if isinstance(inner_data, dict):
                    return inner_data.get("dramas") or inner_data.get("list") or []
                elif isinstance(inner_data, list):
                    return inner_data
                return data.get("dramas") or []
            return []
        except Exception as e:
            logger.error(f"Error searching for {query}: {e}")
            return []

async def get_video_url(book_id: str, chapter_id: str, lang="in"):
    """Fetches the actual play URL for a specific chapter with retry logic."""
    url = f"{BASE_URL}/play/{book_id}/{chapter_id}"
    params = {
        "lang": lang,
        "code": AUTH_CODE
    }
    
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                video_url = data.get("videoUrl") or data.get("url")
                if video_url:
                    return video_url
                
                # If success but no URL, wait and retry?
                await asyncio.sleep(1)
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Error fetching video URL for {book_id}/{chapter_id}: {e}")
                await asyncio.sleep(2)
        return None
