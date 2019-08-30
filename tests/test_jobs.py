from unittest.mock import MagicMock, patch

import pytest

from lims_etl.jobs import sync_partition, verify_partition
from lims_etl.scraper import HTTPScraper


def test_scrape_all_stops_at_reported_last_page():
    scraper = HTTPScraper('http://example.test')
    scraper.authenticated = True
    first = MagicMock(text='Pagina 1 de 2')
    last = MagicMock(text='Pagina 2 de 2')
    with patch.object(scraper, 'get_consulta', side_effect=[first, last]) as get_page:
        with patch.object(scraper, 'parse_current_page', side_effect=[
                [{'Folio': '1', 'ReceivedAt': '20/03/2019'}],
                [{'Folio': '2', 'ReceivedAt': '20/03/2019'}]]):
            assert len(scraper.scrape_all()) == 2
    assert get_page.call_count == 2


def test_scrape_all_rejects_repeated_page():
    scraper = HTTPScraper('http://example.test')
    scraper.authenticated = True
    record = [{'Folio': '1', 'ReceivedAt': '20/03/2019'}]
    with patch.object(scraper, 'get_consulta', return_value=MagicMock(text='')):
        with patch.object(scraper, 'parse_current_page', return_value=record):
            with pytest.raises(RuntimeError, match='repeated page'):
                scraper.scrape_all()


def test_scrape_all_rejects_failed_next_page():
    scraper = HTTPScraper('http://example.test')
    scraper.authenticated = True
    with patch.object(scraper, 'get_consulta', side_effect=[MagicMock(text=''), None]):
        with patch.object(scraper, 'parse_current_page',
                          return_value=[{'Folio': '1', 'ReceivedAt': '20/03/2019'}]):
            with pytest.raises(RuntimeError, match='could not be loaded'):
                scraper.scrape_all()


def test_sync_does_not_replace_when_pagination_fails():
    with patch('lims_etl.jobs.HTTPScraper') as scraper_type:
        with patch('lims_etl.jobs.LIMSApiClient') as hub_type:
            scraper_type.return_value.login.return_value = True
            scraper_type.return_value.scrape_all.side_effect = RuntimeError('repeated page')
            with pytest.raises(RuntimeError, match='repeated page'):
                sync_partition('2019-03-20', 'http://lims', 'user', 'password',
                               'http://hub')
            hub_type.return_value.sync_exams_idempotent.assert_not_called()


def test_verify_rejects_changed_total_on_later_page():
    first = MagicMock()
    first.json.return_value = {'total': 101, 'totalPages': 2, 'data': [{}] * 100}
    second = MagicMock()
    second.json.return_value = {'total': 100, 'totalPages': 2, 'data': [{}]}
    with patch('lims_etl.jobs.requests.get', side_effect=[first, second]):
        with pytest.raises(RuntimeError, match='count changed'):
            verify_partition({'date': '2019-03-20', 'synced': 101}, 'http://hub')
