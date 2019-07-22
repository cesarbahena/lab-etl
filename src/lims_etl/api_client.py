"""
API Client for QuimiOSHub cloud synchronization
"""

import requests
import logging
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

    def sync_samples(self, samples: List[Dict]) -> int:
        """
        Sync samples to cloud API
        Returns number of samples successfully synced
        """
        if not samples:
            reg.info("No samples to sync")
            return 0

        synced_count = 0

        for sample in samples:
            try:
                # Convert sample format to API format
                api_sample = self._convert_sample_format(sample)

                response = self.session.post(
                    f'{self.base_url}/api/samples',
                    json=api_sample,
                    timeout=10
                )

                if response.status_code in [200, 201]:
                    synced_count += 1
                    reg.debug(f"Synced sample {sample.get('_lblFolioGrd')}")
                elif response.status_code == 409:
                    # Duplicate - already exists
                    reg.debug(f"Sample {sample.get('_lblFolioGrd')} already exists in cloud")
                    synced_count += 1
                else:
                    reg.warning(f"Failed to sync sample: HTTP {response.status_code}")

            except Exception as e:
                reg.error(f"Error syncing sample: {e}")
                continue

        reg.info(f"Successfully synced {synced_count}/{len(samples)} samples to cloud")
        return synced_count

    def _convert_sample_format(self, sample: Dict) -> Dict:
        """Convert ETL sample format to API format"""
        return {
            'fechaGrd': self._format_datetime(sample.get('_lblFechaGrd')),
            'fechaRecep': self._format_datetime(sample.get('_lblFechaRecep')),
            'folioGrd': int(sample.get('_lblFolioGrd', 0)),
            'clienteGrd': int(sample.get('_lblClienteGrd', 0)),
            'pacienteGrd': int(sample.get('_lblPacienteGrd', 0)),
            'estPerGrd': int(sample.get('_lblEstPerGrd', 0)),
            'label1': str(sample.get('_Label1', '')),
            'fecCapRes': self._format_datetime(sample.get('_lblFecCapRes')),
            'fecLibera': self._format_datetime(sample.get('_lblFecLibera')),
            'sucProc': str(sample.get('_lblSucProc', '')),
            'maquilador': str(sample.get('_lblMaquilador', '')),
            'label3': str(sample.get('_Label3', '')),
            'fecNac': self._format_date(sample.get('_lblFecNac'))
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
