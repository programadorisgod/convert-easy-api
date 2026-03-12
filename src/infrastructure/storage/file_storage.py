"""File storage management for temporary file handling.

Manages the complete lifecycle of uploaded files:
- Saving individual chunks for large file uploads
- Assembling chunks into complete files
- Providing secure file access
- Streaming files for downloads
- Automatic cleanup and TTL enforcement

Privacy guarantees:
- Files stored with random UUID names (no original filenames)
- No file content logging
- Immediate deletion after download or TTL expiry
- Stored in /tmp or configured temp directory
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncGenerator

import aiofiles
import aiofiles.os

from shared.config import get_settings
from shared.exceptions import ChunkAssemblyError, JobNotFoundError


logger = logging.getLogger(__name__)


class FileStorage:
    """Manages temporary file storage with chunk support.

    File naming convention:
    - Chunks: {file_id}_chunk_{index}
    - Assembled: {file_id}
    - Output: {file_id}_out

    All files stored in configured temp directory (/tmp/easy_convert by default).
    """

    def __init__(self):
        """Initialize file storage."""
        self.settings = get_settings()
        self.temp_dir = self.settings.get_temp_dir()
        logger.info(f"FileStorage initialized with temp dir: {self.temp_dir}")

    def _get_chunk_path(self, file_id: str, chunk_index: int) -> Path:
        """Get path for a specific chunk file.

        Args:
            file_id: File identifier
            chunk_index: Chunk index (0-based)

        Returns:
            Path to chunk file
        """
        return self.temp_dir / f"{file_id}_chunk_{chunk_index}"

    def _get_file_path(self, file_id: str) -> Path:
        """Get path for assembled input file.

        Args:
            file_id: File identifier

        Returns:
            Path to file
        """
        return self.temp_dir / file_id

    def _get_output_path(self, file_id: str) -> Path:
        """Get path for converted output file.

        Args:
            file_id: File identifier

        Returns:
            Path to output file
        """
        return self.temp_dir / f"{file_id}_out"

    async def save_chunk(
        self, file_id: str, chunk_index: int, chunk_data: bytes
    ) -> Path:
        """Save a file chunk to temporary storage.

        Args:
            file_id: File identifier (UUID)
            chunk_index: Chunk index (0-based)
            chunk_data: Raw chunk bytes

        Returns:
            Path where chunk was saved

        Raises:
            IOError: If chunk cannot be saved
        """
        try:
            chunk_path = self._get_chunk_path(file_id, chunk_index)

            # Write chunk atomically (write to temp, then rename)
            temp_path = chunk_path.with_suffix(".tmp")

            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(chunk_data)

            # Atomic rename
            await aiofiles.os.rename(temp_path, chunk_path)

            chunk_size_mb = len(chunk_data) / (1024 * 1024)
            logger.info(
                f"Saved chunk {chunk_index} for file {file_id} ({chunk_size_mb:.2f} MB)"
            )

            return chunk_path

        except Exception as e:
            logger.error(
                f"Failed to save chunk {chunk_index} for file {file_id}: {e}",
                exc_info=True,
            )
            raise IOError(f"Failed to save chunk: {e}")

    async def assemble_chunks(self, file_id: str, total_chunks: int) -> Path:
        """Assemble chunks into a single file.

        Args:
            file_id: File identifier
            total_chunks: Expected number of chunks

        Returns:
            Path to assembled file

        Raises:
            ChunkAssemblyError: If chunks are missing or assembly fails
        """
        try:
            # Verify all chunks exist
            missing_chunks = []
            for i in range(total_chunks):
                chunk_path = self._get_chunk_path(file_id, i)
                if not chunk_path.exists():
                    missing_chunks.append(i)

            if missing_chunks:
                raise ChunkAssemblyError(
                    f"Missing chunks: {missing_chunks}. Expected {total_chunks} chunks."
                )

            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Assemble chunks into output file
            output_path = self._get_file_path(file_id)
            temp_output = output_path.with_suffix(".tmp")

            async with aiofiles.open(temp_output, "wb") as out_file:
                for i in range(total_chunks):
                    chunk_path = self._get_chunk_path(file_id, i)

                    async with aiofiles.open(chunk_path, "rb") as chunk_file:
                        # Stream chunk to output file
                        while True:
                            data = await chunk_file.read(1024 * 1024)  # 1MB buffer
                            if not data:
                                break
                            await out_file.write(data)

            # Atomic rename
            await aiofiles.os.rename(temp_output, output_path)

            # Get file size
            file_size = output_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            logger.info(
                f"Assembled {total_chunks} chunks into file {file_id} "
                f"({file_size_mb:.2f} MB)"
            )

            # Clean up chunks in background
            asyncio.create_task(self.cleanup_chunks(file_id, total_chunks))

            return output_path

        except ChunkAssemblyError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to assemble chunks for file {file_id}: {e}", exc_info=True
            )
            raise ChunkAssemblyError(f"Assembly failed: {e}")

    async def save_file(self, file_id: str, file_data: bytes) -> Path:
        """Save a complete file (no chunking).

        Used for files under 10MB that don't need chunking.

        Args:
            file_id: File identifier (UUID)
            file_data: Complete file bytes

        Returns:
            Path where file was saved
        """
        try:
            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            file_path = self._get_file_path(file_id)
            temp_path = file_path.with_suffix(".tmp")

            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(file_data)

            await aiofiles.os.rename(temp_path, file_path)

            file_size_mb = len(file_data) / (1024 * 1024)
            logger.info(f"Saved file {file_id} ({file_size_mb:.2f} MB)")

            return file_path

        except Exception as e:
            logger.error(f"Failed to save file {file_id}: {e}", exc_info=True)
            raise IOError(f"Failed to save file: {e}")

    async def get_file(self, file_id: str) -> Path:
        """Get path to input file.

        Args:
            file_id: File identifier

        Returns:
            Path to file

        Raises:
            JobNotFoundError: If file doesn't exist
        """
        file_path = self._get_file_path(file_id)

        if not file_path.exists():
            raise JobNotFoundError(file_id)

        return file_path

    async def get_output(self, file_id: str) -> Path:
        """Get path to converted output file.

        Args:
            file_id: File identifier

        Returns:
            Path to output file

        Raises:
            JobNotFoundError: If output doesn't exist
        """
        output_path = self._get_output_path(file_id)

        if not output_path.exists():
            raise JobNotFoundError(file_id)

        return output_path

    async def stream_file(
        self,
        file_path: Path,
        chunk_size: int = 1024 * 1024,  # 1MB chunks
    ) -> AsyncGenerator[bytes, None]:
        """Stream file in chunks for download.

        Args:
            file_path: Path to file to stream
            chunk_size: Size of chunks to stream (default 1MB)

        Yields:
            File chunks as bytes
        """
        try:
            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        except Exception as e:
            logger.error(f"Failed to stream file {file_path}: {e}", exc_info=True)
            raise

    async def cleanup_chunks(self, file_id: str, total_chunks: int) -> None:
        """Delete chunk files after assembly.

        Args:
            file_id: File identifier
            total_chunks: Number of chunks to delete
        """
        try:
            for i in range(total_chunks):
                chunk_path = self._get_chunk_path(file_id, i)
                if chunk_path.exists():
                    await aiofiles.os.remove(chunk_path)

        except Exception as e:
            logger.error(f"Failed to cleanup chunks for file {file_id}: {e}")

    async def cleanup_file(self, file_id: str, include_output: bool = True) -> None:
        """Delete input file and optionally output file.

        Args:
            file_id: File identifier
            include_output: Whether to also delete output file
        """
        try:
            deleted = []

            # Delete input file
            input_path = self._get_file_path(file_id)
            if input_path.exists():
                await aiofiles.os.remove(input_path)
                deleted.append("input")

            # Delete output file if requested
            if include_output:
                output_path = self._get_output_path(file_id)
                if output_path.exists():
                    await aiofiles.os.remove(output_path)
                    deleted.append("output")

            if deleted:
                logger.info(f"Cleaned up {', '.join(deleted)} file(s) for {file_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup files for {file_id}: {e}")

    async def cleanup_old_files(self, max_age_hours: int | None = None) -> int:
        """Delete files older than specified age.

        Args:
            max_age_hours: Delete files older than this many hours
                          (defaults to settings.job_cleanup_hours)

        Returns:
            Number of files deleted
        """
        if max_age_hours is None:
            max_age_hours = self.settings.job_cleanup_hours

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            deleted = 0

            # Scan temp directory
            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    # Get file modification time
                    mtime = datetime.fromtimestamp(
                        file_path.stat().st_mtime, tz=timezone.utc
                    )

                    if mtime < cutoff_time:
                        await aiofiles.os.remove(file_path)
                        deleted += 1

            if deleted > 0:
                logger.info(
                    f"Cleaned up {deleted} old files (older than {max_age_hours}h)"
                )

            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}", exc_info=True)
            return 0

    def file_exists(self, file_id: str) -> bool:
        """Check if input file exists.

        Args:
            file_id: File identifier

        Returns:
            True if file exists
        """
        return self._get_file_path(file_id).exists()

    def output_exists(self, file_id: str) -> bool:
        """Check if output file exists.

        Args:
            file_id: File identifier

        Returns:
            True if output exists
        """
        return self._get_output_path(file_id).exists()

    def get_file_size(self, file_id: str) -> int:
        """Get size of input file in bytes.

        Args:
            file_id: File identifier

        Returns:
            File size in bytes

        Raises:
            JobNotFoundError: If file doesn't exist
        """
        file_path = self._get_file_path(file_id)

        if not file_path.exists():
            raise JobNotFoundError(file_id)

        return file_path.stat().st_size

    def get_output_size(self, file_id: str) -> int:
        """Get size of output file in bytes.

        Args:
            file_id: File identifier

        Returns:
            File size in bytes

        Raises:
            JobNotFoundError: If output doesn't exist
        """
        output_path = self._get_output_path(file_id)

        if not output_path.exists():
            raise JobNotFoundError(file_id)

        return output_path.stat().st_size


# Singleton instance
_file_storage: FileStorage | None = None


def get_file_storage() -> FileStorage:
    """Get file storage singleton instance."""
    global _file_storage
    if _file_storage is None:
        _file_storage = FileStorage()
    return _file_storage
