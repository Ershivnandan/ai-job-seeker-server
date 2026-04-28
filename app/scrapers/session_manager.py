import json
import os
from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    def __init__(self):
        self.cookies_dir = os.path.join(settings.STORAGE_PATH, "cookies")
        os.makedirs(self.cookies_dir, exist_ok=True)

    def get_cookies_path(self, platform: str, user_id: str) -> str:
        return os.path.join(self.cookies_dir, f"{platform}_{user_id}.json")

    def has_session(self, platform: str, user_id: str) -> bool:
        path = self.get_cookies_path(platform, user_id)
        return os.path.exists(path)

    def load_cookies(self, platform: str, user_id: str) -> Optional[list[dict]]:
        path = self.get_cookies_path(platform, user_id)
        try:
            with open(path, "r") as f:
                cookies = json.load(f)
            logger.info(f"Loaded session for {platform}/{user_id}: {len(cookies)} cookies")
            return cookies
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save_cookies(self, platform: str, user_id: str, cookies: list[dict]):
        path = self.get_cookies_path(platform, user_id)
        with open(path, "w") as f:
            json.dump(cookies, f)
        logger.info(f"Saved session for {platform}/{user_id}: {len(cookies)} cookies")

    def delete_session(self, platform: str, user_id: str):
        path = self.get_cookies_path(platform, user_id)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted session for {platform}/{user_id}")


session_manager = SessionManager()
