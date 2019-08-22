"""
Unit tests for QuimiOSHub API client.
Tests verify contract with lab-hub API, not implementation.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
import pandas as pd

from lims_etl.api_client import LIMSApiClient


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def api_client_with_mock(mock_session):
    client = LIMSApiClient.__new__(LIMSApiClient)
    client.base_url = "http://localhost:8080"
    client.api_key = "test_key"
    client.session = mock_session
    return client


class TestHealthCheck:
    """API health verification."""

    def test_health_check_returns_true_on_success(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.health_check()
        assert result is True

    def test_health_check_returns_false_on_failure(self, mock_session):
        mock_session.get.side_effect = Exception("Connection failed")

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.health_check()
        assert result is False


class TestSampleSync:
    """Sample data synchronization."""

    def test_sync_samples_returns_count(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 201
        mock_session.post.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [
            {'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
             'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': pd.NaT,
             'ProcessedAt': pd.NaT, 'ValidatedAt': pd.NaT, 'Location': 'Lab',
             'Outsourcer': 'Test', 'Priority': 'Normal', 'BirthDate': pd.NaT}
        ]

        result = client.sync_samples(samples)
        assert result == 1

    def test_sync_samples_returns_zero_for_empty_list(self, mock_session):
        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.sync_samples([])
        assert result == 0

    def test_sync_samples_handles_conflict(self, mock_session):
        mock_delete = Mock()
        mock_delete.status_code = 200
        mock_delete.json.return_value = {'deleted': 0}

        mock_response = Mock()
        mock_response.status_code = 201

        mock_session.delete.return_value = mock_delete
        mock_session.post.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [{'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
                   'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': pd.NaT,
                   'ProcessedAt': pd.NaT, 'ValidatedAt': pd.NaT, 'Location': 'Lab',
                   'Outsourcer': 'Test', 'Priority': 'Normal', 'BirthDate': pd.NaT}]

        result = client.sync_samples(samples)
        assert result == 1


class TestIdempotentSync:
    """Idempotent sync with partition support."""

    def test_sync_samples_idempotent_returns_stats(self, mock_session):
        mock_delete = Mock()
        mock_delete.status_code = 200
        mock_delete.json.return_value = {'deleted': 5}

        mock_post = Mock()
        mock_post.status_code = 201

        mock_session.delete.return_value = mock_delete
        mock_session.post.return_value = mock_post

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [
            {'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
             'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': pd.NaT,
             'ProcessedAt': pd.NaT, 'ValidatedAt': pd.NaT, 'Location': 'Lab',
             'Outsourcer': 'Test', 'Priority': 'Normal', 'BirthDate': pd.NaT}
        ]

        result = client.sync_samples_idempotent(samples, '2024-01-15')

        assert result['partition_date'] == '2024-01-15'
        assert result['total'] == 1
        assert result['inserted'] == 1
        assert 'deleted' in result

    def test_sync_idempotent_handles_empty_samples(self, mock_session):
        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.sync_samples_idempotent([], '2024-01-15')

        assert result['total'] == 0
        assert result['inserted'] == 0

    def test_sync_idempotent_retry_on_failure(self, mock_session):
        mock_delete = Mock()
        mock_delete.status_code = 200
        mock_delete.json.return_value = {'deleted': 0}

        mock_session.delete.return_value = mock_delete

        # First call raises, second succeeds
        mock_post = Mock()
        mock_post.status_code = 201

        def side_effect(*args, **kwargs):
            if not hasattr(side_effect, 'called'):
                side_effect.called = True
                raise Exception("Timeout")
            return mock_post

        mock_session.post.side_effect = side_effect

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [{'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
                   'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': pd.NaT,
                   'ProcessedAt': pd.NaT, 'ValidatedAt': pd.NaT, 'Location': 'Lab',
                   'Outsourcer': 'Test', 'Priority': 'Normal', 'BirthDate': pd.NaT}]

        with patch('lims_etl.api_client.time.sleep'):
            result = client.sync_samples_idempotent(samples, '2024-01-15')

        assert result['inserted'] == 1
        assert result['failed'] == 0


class TestDeletePartition:
    """Partition deletion for idempotency."""

    def test_delete_partition_returns_count(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'deleted': 10}
        mock_session.delete.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.delete_partition_samples('2024-01-15')
        assert result == 10

    def test_delete_partition_returns_zero_when_not_found(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.delete.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.delete_partition_samples('2024-01-15')
        assert result == 0

    def test_delete_partition_with_client_filter(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'deleted': 5}
        mock_session.delete.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        result = client.delete_partition_samples('2024-01-15', client_id=101)
        assert result == 5

        call_args = mock_session.delete.call_args
        assert 'client_id' in call_args.kwargs['params']


class TestDateFormatting:
    """Datetime formatting for API."""

    def test_format_datetime_handles_nat(self, mock_session):
        client = LIMSApiClient.__new__(LIMSApiClient)
        result = client._format_datetime(pd.NaT)
        assert result is None

    def test_format_datetime_handles_none(self, mock_session):
        client = LIMSApiClient.__new__(LIMSApiClient)
        result = client._format_datetime(None)
        assert result is None

    def test_format_date_handles_nat(self, mock_session):
        client = LIMSApiClient.__new__(LIMSApiClient)
        result = client._format_date(pd.NaT)
        assert result is None

    def test_format_date_handles_none(self, mock_session):
        client = LIMSApiClient.__new__(LIMSApiClient)
        result = client._format_date(None)
        assert result is None