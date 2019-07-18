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


def test_duplicate_handling(test_db):
    """Test that duplicate samples are handled properly"""
    sample_data = [{
        '_lblFechaGrd': datetime(2023, 1, 1, 10, 0, 0),
        '_lblFechaRecep': datetime(2023, 1, 1, 11, 0, 0),
        '_lblFolioGrd': 12345,
        '_lblClienteGrd': 101,
        '_Label1': 'Original Label'
    }]
    
    # Insert first time
    count1 = test_db.save_samples(sample_data)
    assert count1 == 1
    assert test_db.get_sample_count() == 1
    
    # Insert same data again (should update, not duplicate)
    sample_data[0]['_Label1'] = 'Updated Label'
    count2 = test_db.save_samples(sample_data)
    assert count2 == 1
    assert test_db.get_sample_count() == 1  # Still only 1 record
    
    # Verify the data was updated
    session = test_db.get_session()
    try:
        from lims_etl.database import Sample
        sample = session.query(Sample).first()
        assert sample.label1 == 'Updated Label'
    finally:
        session.close()


def test_upsert_mixed_data(test_db):
    """Test upsert with mix of new and existing data"""
    # Insert initial data
    initial_data = [{
        '_lblFechaRecep': datetime(2023, 1, 1, 11, 0, 0),
        '_lblFolioGrd': 100,
        '_lblClienteGrd': 101,
        '_Label1': 'Sample 1'
    }]
    test_db.save_samples(initial_data)
    assert test_db.get_sample_count() == 1
    
    # Mix of existing and new data
    mixed_data = [
        {  # This exists - should update
            '_lblFechaRecep': datetime(2023, 1, 1, 11, 0, 0),
            '_lblFolioGrd': 100,
            '_lblClienteGrd': 101,
            '_Label1': 'Updated Sample 1'
        },
        {  # This is new - should insert
            '_lblFechaRecep': datetime(2023, 1, 2, 11, 0, 0),
            '_lblFolioGrd': 200,
            '_lblClienteGrd': 102,
            '_Label1': 'Sample 2'
        }
    ]
    
    count = test_db.save_samples(mixed_data)
    assert count == 2  # Processed 2 records
    assert test_db.get_sample_count() == 2  # Total 2 unique records