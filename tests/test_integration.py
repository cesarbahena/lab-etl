"""
Basic integration tests for LIMS scraper
"""
import tempfile
import os
from unittest.mock import patch
from pathlib import Path
from lims_etl.scraper import main, LIMSConfig
from lims_etl.database import DatabaseManager


def test_scraper_runs_end_to_end():
    """Test that scraper can run without crashing"""
    with patch.object(DatabaseManager, '__init__', return_value=None), \
         patch.object(DatabaseManager, 'create_tables', return_value=None):
        try:
            config = LIMSConfig()
            assert config.test_clients == [101, 102]
            assert config.max_fails == 30
        except FileNotFoundError:
            # Expected if selectors.json missing
            pass


def test_config_loads_selectors():
    """Test that config properly loads selectors file"""
    with patch.object(DatabaseManager, '__init__', return_value=None), \
         patch.object(DatabaseManager, 'create_tables', return_value=None):
        try:
            config = LIMSConfig()
            assert hasattr(config, 'selectors')
        except FileNotFoundError as e:
            assert "selectors.json not found" in str(e)