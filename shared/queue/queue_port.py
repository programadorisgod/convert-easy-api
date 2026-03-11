"""Queue port interface following Hexagonal Architecture.

This defines the contract that any queue implementation must fulfill,
allowing us to swap Redis/BullMQ for other solutions without changing
business logic.
"""

from abc import ABC, abstractmethod
from typing import Any


class QueuePort(ABC):
    """Abstract base class for job queue operations."""
    
    @abstractmethod
    async def enqueue(
        self,
        job_id: str,
        job_data: dict[str, Any],
        priority: int = 0
    ) -> str:
        """Enqueue a new job for processing.
        
        Args:
            job_id: Unique job identifier
            job_data: Job payload data
            priority: Job priority (higher = more urgent)
            
        Returns:
            Queue job ID
        """
        pass
    
    @abstractmethod
    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get current status of a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status dict or None if not found
        """
        pass
    
    @abstractmethod
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Update job status and metadata.
        
        Args:
            job_id: Job identifier
            status: New status
            metadata: Additional metadata to store
        """
        pass
    
    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancelled, False if not found or already complete
        """
        pass
    
    @abstractmethod
    async def get_queue_size(self) -> int:
        """Get number of jobs waiting in queue.
        
        Returns:
            Count of pending jobs
        """
        pass
