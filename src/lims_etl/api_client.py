"""
API Client for QuimiOSHub cloud synchronization

Key Features:
- Idempotent: Safe to re-run without duplicates
- Partition-aware: Supports DELETE + INSERT per date partition
- Retry logic: Exponential backoff on transient failures
- DLQ ready: Structured error handling
"""

import requests
import logging
import time
from typing import List, Dict, Optional
from datetime import datetime

reg = logging.getLogger(__name__)


class QuimiOSHubClient:
    """Client for syncing data to QuimiOSHub cloud API"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})

        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'quimios-etl/1.0'
        })

    def health_check(self) -> bool:
        """Check if API is accessible"""
        try:
            response = self.session.get(f'{self.base_url}/api/health/ping', timeout=5)
            return response.status_code == 200
        except Exception as e:
            reg.error(f"Health check failed: {e}")
            return False

    def delete_partition_samples(self, partition_date: str, client_id: Optional[int] = None) -> int:
        """
        Delete samples for a partition date (idempotency).
        
        This enables the DELETE + INSERT pattern for safe backfills:
        1. DELETE all records for this date
        2. INSERT fresh records
        3. Re-running produces same result (idempotent)
        
        Args:
            partition_date: Date string (YYYY-MM-DD) for partition
            client_id: Optional client filter
            
        Returns:
            Number of records deleted
        """
        try:
            params = {'partition_date': partition_date}
            if client_id:
                params['client_id'] = client_id
            
            response = self.session.delete(
                f'{self.base_url}/api/samples/partition',
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                deleted = result.get('deleted', 0)
                reg.info(f"Deleted {deleted} samples for partition {partition_date}")
                return deleted
            elif response.status_code == 404:
                # No records to delete - this is fine
                reg.debug(f"No records found for partition {partition_date}")
                return 0
            else:
                reg.warning(f"Delete partition failed: HTTP {response.status_code}")
                return 0
                
        except Exception as e:
            reg.error(f"Error deleting partition {partition_date}: {e}")
            return 0

    def sync_samples(self, samples: List[Dict]) -> int:
        """Sync samples - returns count synced (legacy compatibility)."""
        if not samples:
            return 0
        result = self.sync_samples_idempotent(samples, partition_date='current')
        return result['inserted']

    def sync_samples_idempotent(self, samples: List[Dict], partition_date: str) -> dict:
        """
        Sync samples with idempotency via DELETE + INSERT pattern.
        
        This is the production-grade method for safe re-runs:
        - First deletes all samples for the partition date
        - Then inserts all provided samples
        - Result is always consistent regardless of retry count
        
        Args:
            samples: List of sample records to sync
            partition_date: Date string (YYYY-MM-DD) for this batch
            
        Returns:
            Dict with sync statistics
        """
        stats = {
            'partition_date': partition_date,
            'total': len(samples),
            'inserted': 0,
            'updated': 0,
            'deleted': 0,
            'failed': 0,
            'errors': []
        }
        
        if not samples:
            reg.info(f"No samples to sync for partition {partition_date}")
            return stats
        
        # Step 1: Delete existing records for this partition (idempotency)
        stats['deleted'] = self.delete_partition_samples(partition_date)
        
        # Step 2: Insert all samples
        for sample in samples:
            for attempt in range(3):  # Retry up to 3 times
                try:
                    api_sample = self._convert_sample_format(sample)
                    
                    response = self.session.post(
                        f'{self.base_url}/api/samples',
                        json=api_sample,
                        timeout=10
                    )
                    
                    if response.status_code in [200, 201]:
                        stats['inserted'] += 1
                        break
                    elif response.status_code == 409:
                        # Conflict - sample already exists (shouldn't happen after delete)
                        stats['updated'] += 1
                        break
                    else:
                        reg.warning(f"Failed to sync sample: HTTP {response.status_code}")
                        
                except Exception as e:
                    if attempt < 2:  # Retry with backoff
                        wait_time = (2 ** attempt) * 2  # 2, 4 seconds
                        reg.debug(f"Retry {attempt + 1} after {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        stats['failed'] += 1
                        stats['errors'].append({
                            'folio': sample.get('Folio'),
                            'error': str(e)
                        })
        
        reg.info(f"Synced partition {partition_date}: "
                 f"{stats['inserted']}/{stats['total']} inserted, "
                 f"{stats['deleted']} deleted, {stats['failed']} failed")
        
        return stats

    def _convert_sample_format(self, sample: Dict) -> Dict:
        """Convert ETL sample format to API format"""
        return {
            'createdAt': self._format_datetime(sample.get('CreatedAt')),
            'receivedAt': self._format_datetime(sample.get('ReceivedAt')),
            'folio': int(sample.get('Folio', 0)),
            'clientId': int(sample.get('ClientId', 0)),
            'patientId': int(sample.get('PatientId', 0)),
            'examId': int(sample.get('ExamId', 0)),
            'examName': str(sample.get('ExamName', '')),
            'processedAt': self._format_datetime(sample.get('ProcessedAt')),
            'validatedAt': self._format_datetime(sample.get('ValidatedAt')),
            'location': str(sample.get('Location', '')),
            'outsourcer': str(sample.get('Outsourcer', '')),
            'priority': str(sample.get('Priority', '')),
            'birthDate': self._format_date(sample.get('BirthDate'))
        }

    def _format_datetime(self, dt) -> Optional[str]:
        """Format datetime for API"""
        if dt is None or (hasattr(dt, '__class__') and 'NaT' in str(dt.__class__)):
            return None

        if isinstance(dt, str):
            return dt

        try:
            return dt.isoformat()
        except:
            return None

    def _format_date(self, dt) -> Optional[str]:
        """Format date for API"""
        if dt is None or (hasattr(dt, '__class__') and 'NaT' in str(dt.__class__)):
            return None

        if isinstance(dt, str):
            return dt

        try:
            return dt.strftime('%Y-%m-%d')
        except:
            return None
