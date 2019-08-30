"""Scheduled exam synchronization and post-write verification."""

import os
from datetime import datetime, timedelta

import requests

from .api_client import LIMSApiClient
from .scraper import HTTPScraper


def sync_partition(day, lims_url=None, username=None, password=None,
                   hub_url=None, api_key=None):
    """Replace one complete received-date partition, or leave it untouched."""
    lims_url = lims_url or os.getenv('LIMS_BASE_URL')
    username = username or os.getenv('LIMS_USERNAME')
    password = password or os.getenv('LIMS_PASSWORD')
    hub_url = hub_url or os.getenv('HUB_API_URL')
    api_key = api_key or os.getenv('HUB_API_KEY')
    if not all((lims_url, username, password, hub_url)):
        raise ValueError('LIMS and Hub connection settings are required')
    scraper = HTTPScraper(lims_url, username, password)
    if not scraper.login():
        raise RuntimeError('LIMS login failed')
    records = scraper.scrape_all()
    client = LIMSApiClient(hub_url, api_key)
    exams = client.exams_for_partition(records, day)
    if not exams:
        raise RuntimeError('No exams found for {}; partition unchanged'.format(day))
    result = client.sync_exams_idempotent(exams, day)
    if result['failed']:
        raise RuntimeError('Exam sync failed for {}'.format(day))
    return {'date': day, 'scraped': len(records),
            'synced': result['inserted'] + result['updated']}


def verify_partition(summary, hub_url=None):
    """Verify the complete Hub page set after an atomic replacement."""
    hub_url = hub_url or os.getenv('HUB_API_URL')
    if not hub_url:
        raise ValueError('HUB_API_URL is required')
    start = datetime.strptime(summary['date'], '%Y-%m-%d')
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    params = {'startDate': start.isoformat(), 'endDate': end.isoformat(),
              'pageSize': 100}
    expected_total = summary['synced']
    all_exams = []
    total_pages = None
    for page in range(1, 1001):
        response = requests.get('{}/api/exams'.format(hub_url.rstrip('/')),
                                params=dict(params, page=page), timeout=10)
        response.raise_for_status()
        body = response.json()
        if body['total'] != expected_total:
            raise RuntimeError('Hub partition count changed during verification')
        if total_pages is None:
            total_pages = body['totalPages']
        if body['totalPages'] != total_pages:
            raise RuntimeError('Hub page count changed during verification')
        all_exams.extend(body['data'])
        if page >= total_pages:
            break
    else:
        raise RuntimeError('Hub partition exceeded 1000 pages')
    required = ('folio', 'clientId', 'patientId', 'examName')
    if (len(all_exams) != expected_total or
            any(any(exam.get(field) is None for field in required)
                for exam in all_exams)):
        raise RuntimeError('Hub partition content failed verification')
    return {'date': summary['date'], 'verified': len(all_exams)}
