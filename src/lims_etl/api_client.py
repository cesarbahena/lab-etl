"""
API Client for LIMS data synchronization

Key Features:
- Idempotent: Safe to re-run without duplicates
- Partition-aware: Replaces each date partition in one Hub transaction
- Retry logic: Exponential backoff on transient failures
- DLQ ready: Structured error handling
"""

import requests
import logging
import time
from typing import List, Dict, Optional
from datetime import date, datetime

reg = logging.getLogger(__name__)


class LIMSApiClient:
    """Client for syncing exam data to LIMS Hub API"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})

        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'lims-etl/1.0'
        })

    def health_check(self) -> bool:
        """Check if API is accessible"""
        try:
            response = self.session.get(f'{self.base_url}/api/health/ping', timeout=5)
            return response.status_code == 200
        except Exception as e:
            reg.error(f"Health check failed: {e}")
            return False

    def delete_partition_exams(self, partition_date: str, client_id: Optional[int] = None) -> int:
        """
        Delete a partition through the compatibility endpoint.

        Use sync_exams_idempotent for atomic replacement. A separate DELETE
        followed by POST requests does not preserve the old data on failure.
        
        Args:
            partition_date: Date string (YYYY-MM-DD) for partition
            client_id: Optional client filter
            
        Returns:
            Number of records deleted
        """
        try:
            params = {'partitionDate': partition_date}
            if client_id is not None:
                params['clientId'] = client_id
            
            response = self.session.delete(
                f'{self.base_url}/api/exams/partition',
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Partition delete failed: HTTP {response.status_code}")

            deleted = response.json()['deleted']
            if not isinstance(deleted, int) or deleted < 0:
                raise ValueError("Partition delete returned an invalid count")
            reg.info(f"Deleted {deleted} exams for partition {partition_date}")
            return deleted
                
        except Exception as e:
            reg.error(f"Error deleting partition {partition_date}: {e}")
            raise

    def sync_exams(self, exams: List[Dict]) -> int:
        """Replace complete client/date groups and return the count synced."""
        if not exams:
            return 0

        groups = {}
        for exam in exams:
            received_at = self._format_datetime(exam.get('ReceivedAt'))
            if received_at is None:
                raise ValueError(f"Exam {exam.get('Folio')} has no ReceivedAt date")
            client_id = int(exam['ClientId'])
            if client_id <= 0:
                raise ValueError(f"Exam {exam.get('Folio')} has no client ID")
            groups.setdefault((received_at[:10], client_id), []).append(exam)

        synced = 0
        for (partition_date, client_id), group in groups.items():
            result = self.sync_exams_idempotent(group, partition_date, client_id=client_id)
            synced += result['inserted']
        return synced

    def exams_for_partition(self, exams: List[Dict], partition_date: str) -> List[Dict]:
        """Keep exams received on one date, rejecting rows without a usable date."""
        date.fromisoformat(partition_date)
        selected = []
        for exam in exams:
            received_at = self._format_datetime(exam.get('ReceivedAt'))
            if received_at is None:
                raise ValueError(f"Exam {exam.get('Folio')} has no ReceivedAt date")
            if received_at[:10] == partition_date:
                selected.append(exam)
        return selected

    def sync_exams_idempotent(self, exams: List[Dict], partition_date: str,
                              client_id: Optional[int] = None) -> dict:
        """
        Replace one Hub partition in a single request and database transaction.
        
        Args:
            exams: List of exam records to sync
            partition_date: Date string (YYYY-MM-DD) for this batch
            client_id: Optional client filter for a client-specific partition
            
        Returns:
            Dict with sync statistics
        """
        stats = {
            'partition_date': partition_date,
            'total': len(exams),
            'inserted': 0,
            'updated': 0,
            'deleted': 0,
            'failed': 0,
            'errors': []
        }
        
        date.fromisoformat(partition_date)
        api_exams = [self._convert_exam_format(exam) for exam in exams]
        params = {'partitionDate': partition_date}
        if client_id is not None:
            params['clientId'] = client_id

        last_error = None
        for attempt in range(3):
            try:
                response = self.session.post(
                    f'{self.base_url}/api/exams/partition',
                    params=params,
                    json=api_exams,
                    timeout=30
                )
            except requests.RequestException as error:
                last_error = error
            else:
                if response.status_code == 200:
                    result = response.json()
                    deleted = result['deleted']
                    inserted = result['inserted']
                    if (type(deleted) is not int or deleted < 0 or
                            type(inserted) is not int or inserted != len(exams)):
                        raise RuntimeError('Hub returned invalid partition counts')
                    stats['deleted'] = deleted
                    stats['inserted'] = inserted
                    reg.info(f"Replaced partition {partition_date}: "
                             f"{deleted} deleted, {inserted} inserted")
                    return stats

                last_error = RuntimeError(f"Partition replacement failed: HTTP {response.status_code}")
                if response.status_code < 500:
                    raise last_error

            if attempt < 2:
                wait_time = (2 ** attempt) * 2
                reg.debug(f"Retry partition {partition_date} after {wait_time}s: {last_error}")
                time.sleep(wait_time)

        raise RuntimeError(f"Partition replacement failed after retries: {last_error}") from last_error

    # Aliases for backwards compatibility
    sync_samples = sync_exams
    sync_samples_idempotent = sync_exams_idempotent
    delete_partition_samples = delete_partition_exams

    def _convert_exam_format(self, exam: Dict) -> Dict:
        """Convert ETL exam format to API format"""
        return {
            'createdAt': self._format_datetime(exam.get('CreatedAt')),
            'receivedAt': self._format_datetime(exam.get('ReceivedAt')),
            'folio': int(exam.get('Folio', 0)),
            'clientId': int(exam.get('ClientId', 0)),
            'patientId': int(exam.get('PatientId', 0)),
            'examId': int(exam.get('ExamId', 0)),
            'examName': str(exam.get('ExamName', '')),
            'processedAt': self._format_datetime(exam.get('ProcessedAt')),
            'validatedAt': self._format_datetime(exam.get('ValidatedAt')),
            'location': str(exam.get('Location', '')),
            'outsourcer': str(exam.get('Outsourcer', '')),
            'priority': str(exam.get('Priority', '')),
            'birthDate': self._format_date(exam.get('BirthDate'))
        }

    # Alias for backwards compatibility
    _convert_sample_format = _convert_exam_format

    def _format_datetime(self, dt) -> Optional[str]:
        """Format datetime for API"""
        if dt is None or (hasattr(dt, '__class__') and 'NaT' in str(dt.__class__)):
            return None

        if isinstance(dt, str):
            if not dt.strip():
                return None
            for pattern in ('%d/%m/%Y %I:%M:%S %p', '%d-%m-%Y %I:%M:%S %p',
                            '%d/%m/%Y %H:%M:%S', '%d-%m-%Y %H:%M:%S',
                            '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    return datetime.strptime(dt, pattern).isoformat()
                except ValueError:
                    pass
            return datetime.fromisoformat(dt).isoformat()

        try:
            return dt.isoformat()
        except:
            return None

    def _format_date(self, dt) -> Optional[str]:
        """Format date for API"""
        if dt is None or (hasattr(dt, '__class__') and 'NaT' in str(dt.__class__)):
            return None

        if isinstance(dt, str):
            if not dt.strip():
                return None
            for pattern in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
                try:
                    return datetime.strptime(dt, pattern).date().isoformat()
                except ValueError:
                    pass
            raise ValueError(f"Unsupported date format: {dt}")

        try:
            return dt.strftime('%Y-%m-%d')
        except:
            return None
