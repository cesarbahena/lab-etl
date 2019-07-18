"""
Tests for database operations
"""
import pytest
from unittest.mock import patch
from datetime import datetime
from lims_etl.database import DatabaseManager, Sample


@pytest.fixture
def test_db():
    """Create test database manager with in-memory SQLite"""
    db = DatabaseManager("sqlite:///:memory:")
    db.create_tables()
    return db


def test_database_manager_init():
    """Test database manager initialization"""
    with patch.dict('os.environ', {
        'DB_HOST': 'testhost',
        'DB_PORT': '5433',
        'DB_NAME': 'testdb',
        'DB_USER': 'testuser',
        'DB_PASSWORD': 'testpass'
    }):
        db = DatabaseManager()
        url_str = str(db.engine.url)
        assert "postgresql://testuser:" in url_str
        assert "@testhost:5433/testdb" in url_str


def test_save_samples(test_db):
    """Test saving sample data to database"""
    sample_data = [{
        '_lblFechaGrd': datetime(2023, 1, 1, 10, 0, 0),
        '_lblFechaRecep': datetime(2023, 1, 1, 11, 0, 0),
        '_lblFolioGrd': 12345,
        '_lblClienteGrd': 101,
        '_lblPacienteGrd': 202,
        '_lblEstPerGrd': 303,
        '_Label1': 'Test Label',
        '_lblFecCapRes': datetime(2023, 1, 1, 12, 0, 0),
        '_lblFecLibera': datetime(2023, 1, 1, 13, 0, 0),
        '_lblSucProc': 'Branch A',
        '_lblMaquilador': 'Test Maq',
        '_Label3': 'Label 3',
        '_lblFecNac': datetime(1990, 5, 15)
    }]
    
    count = test_db.save_samples(sample_data)
    assert count == 1
    assert test_db.get_sample_count() == 1


def test_get_sample_count(test_db):
    """Test getting sample count from database"""
    assert test_db.get_sample_count() == 0
    
    sample_data = [{'_lblFolioGrd': 123, '_lblClienteGrd': 101}]
    test_db.save_samples(sample_data)
    
    assert test_db.get_sample_count() == 1