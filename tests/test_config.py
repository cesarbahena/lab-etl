"""
Unit tests for LIMS configuration module.
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from lims_etl.config import LIMSConfig


class TestConfigDefaults:
    """Configuration default values."""

    def test_default_username(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert config.username == 'demo_user'

    def test_default_password(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert config.password == 'demo_pass'

    def test_default_sleep_time(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert config.sleep_time == 2

    def test_default_max_empty_pages(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert config.max_empty_pages == 5


class TestConfigOverrides:
    """Configuration from environment variables."""

    def test_lims_username_from_env(self):
        with patch.dict('os.environ', {'LIMS_USERNAME': 'test_user'}):
            config = LIMSConfig()
            assert config.username == 'test_user'

    def test_lims_password_from_env(self):
        with patch.dict('os.environ', {'LIMS_PASSWORD': 'secret'}):
            config = LIMSConfig()
            assert config.password == 'secret'

    def test_sleep_time_from_env(self):
        with patch.dict('os.environ', {'LIMS_SLEEP_TIME': '5'}):
            config = LIMSConfig()
            assert config.sleep_time == 5

    def test_max_empty_pages_from_env(self):
        with patch.dict('os.environ', {'LIMS_MAX_EMPTY_PAGES': '3'}):
            config = LIMSConfig()
            assert config.max_empty_pages == 3


class TestConfigDates:
    """Date range configuration."""

    def test_start_date_default(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            expected = datetime.now() - timedelta(days=1)
            assert (expected - config.start_date).total_seconds() < 5

    def test_end_date_from_env(self):
        with patch.dict('os.environ', {'LIMS_END_DATE': '2021-01-15'}):
            config = LIMSConfig()
            assert config.end_date == datetime(2021, 1, 15)

    def test_custom_start_date_from_env(self):
        with patch.dict('os.environ', {'LIMS_START_DATE': '2023-03-15'}):
            config = LIMSConfig()
            assert config.start_date == datetime(2023, 3, 15)


class TestLocalFixtures:
    """Local fixtures mode configuration."""

    def test_local_fixtures_false_by_default(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert config.use_local_fixtures is False

    def test_local_fixtures_true_from_env(self):
        with patch.dict('os.environ', {'LIMS_USE_LOCAL_FIXTURES': 'true'}):
            config = LIMSConfig()
            assert config.use_local_fixtures is True

    def test_login_url_with_local_fixtures(self, tmp_path):
        with patch.dict('os.environ', {'LIMS_USE_LOCAL_FIXTURES': 'true'}):
            config = LIMSConfig()
            url = config.get_login_url()
            assert url.startswith('file://')
            assert 'login.html' in url

    def test_consulta_url_with_local_fixtures(self, tmp_path):
        with patch.dict('os.environ', {'LIMS_USE_LOCAL_FIXTURES': 'true'}):
            config = LIMSConfig()
            url = config.get_consulta_url()
            assert url.startswith('file://')
            assert 'consulta.html' in url


class TestHubApi:
    """QuimiOSHub API configuration."""

    def test_hub_api_url_from_env(self):
        with patch.dict('os.environ', {'HUB_API_URL': 'http://test:8080'}):
            config = LIMSConfig()
            assert config.hub_api_url == 'http://test:8080'

    def test_hub_api_key_from_env(self):
        with patch.dict('os.environ', {'HUB_API_KEY': 'test_key'}):
            config = LIMSConfig()
            assert config.hub_api_key == 'test_key'


class TestSelectors:
    """UI selectors configuration."""

    def test_selectors_loaded(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert 'GRID_ROW_BASE' in config.selectors
            assert 'LOGIN_USERNAME_FIELD' in config.selectors

    def test_selector_values(self):
        with patch.dict('os.environ', {}, clear=True):
            config = LIMSConfig()
            assert config.selectors['GRID_ROW_BASE'] == 'ctl00_ContentMasterPage_grdConsultaOT_ctl'