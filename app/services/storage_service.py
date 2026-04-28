import os
import hashlib
import aiofiles

from app.config import settings


class StorageService:
    def __init__(self):
        self.base_path = settings.STORAGE_PATH

    def _get_path(self, subfolder: str, filename: str) -> str:
        folder = os.path.join(self.base_path, subfolder)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, filename)

    async def save_resume(self, filename: str, content: bytes) -> tuple[str, str]:
        file_hash = hashlib.sha256(content).hexdigest()
        safe_filename = f"{file_hash[:16]}_{filename}"
        file_path = self._get_path("resumes", safe_filename)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        return file_path, file_hash

    async def save_generated_pdf(self, filename: str, content: bytes) -> str:
        file_path = self._get_path("generated", filename)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return file_path

    async def read_file(self, file_path: str) -> bytes:
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    def delete_file(self, file_path: str) -> bool:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False


storage_service = StorageService()
