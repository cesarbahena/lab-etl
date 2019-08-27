"""
Unit tests for QuimiOSHub API client.
Tests verify contract with lab-hub API, not implementation.
"""

import pytest
import requests
from unittest.mock import MagicMock, patch, Mock
import pandas as pd

from lims_etl.api_client import LIMSApiClient


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.delete.return_value.status_code = 200
    session.delete.return_value.json.return_value = {'deleted': 0}
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = {'deleted': 0, 'inserted': 1}
    return session


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
        mock_response.status_code = 200
        mock_response.json.return_value = {'deleted': 0, 'inserted': 1}
        mock_session.post.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [
            {'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
             'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': '2024-01-15T12:00:00',
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

    def test_sync_samples_uses_partition_endpoint(self, mock_session):
        mock_delete = Mock()
        mock_delete.status_code = 200
        mock_delete.json.return_value = {'deleted': 0}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'deleted': 0, 'inserted': 1}

        mock_session.delete.return_value = mock_delete
        mock_session.post.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [{'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
                   'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': '2024-01-15T12:00:00',
                   'ProcessedAt': pd.NaT, 'ValidatedAt': pd.NaT, 'Location': 'Lab',
                   'Outsourcer': 'Test', 'Priority': 'Normal', 'BirthDate': pd.NaT}]

        result = client.sync_samples(samples)
        assert result == 1
        assert mock_session.post.call_args.args[0].endswith('/api/exams/partition')
        mock_session.delete.assert_not_called()

    def test_sync_samples_keeps_client_dates_separate(self, api_client_with_mock):
        exam = {'Folio': 100001, 'ClientId': 101, 'PatientId': 1,
                'ExamId': 1, 'ExamName': 'Glucose',
                'ReceivedAt': '2024-01-15T12:00:00'}
        exams = [exam,
                 dict(exam, Folio=100002, ClientId=102),
                 dict(exam, Folio=100003, ReceivedAt='2024-01-16T12:00:00')]

        result = api_client_with_mock.sync_exams(exams)

        assert result == 3
        params = [call.kwargs['params'] for call in api_client_with_mock.session.post.call_args_list]
        assert params == [
            {'partitionDate': '2024-01-15', 'clientId': 101},
            {'partitionDate': '2024-01-15', 'clientId': 102},
            {'partitionDate': '2024-01-16', 'clientId': 101},
        ]

    def test_sync_samples_rejects_missing_date_before_writing(self, api_client_with_mock):
        with pytest.raises(ValueError, match='ReceivedAt'):
            api_client_with_mock.sync_exams([{
                'Folio': 100001, 'ClientId': 101, 'ReceivedAt': None
            }])

        api_client_with_mock.session.post.assert_not_called()


class TestIdempotentSync:
    """Idempotent sync with partition support."""

    def test_sync_samples_idempotent_returns_stats(self, mock_session):
        mock_delete = Mock()
        mock_delete.status_code = 200
        mock_delete.json.return_value = {'deleted': 5}

        mock_post = Mock()
        mock_post.status_code = 200
        mock_post.json.return_value = {'deleted': 5, 'inserted': 1}

        mock_session.delete.return_value = mock_delete
        mock_session.post.return_value = mock_post

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [
            {'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
             'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': '2024-01-15T12:00:00',
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

        mock_session.post.return_value.json.return_value = {'deleted': 2, 'inserted': 0}
        result = client.sync_samples_idempotent([], '2024-01-15')

        assert result['total'] == 0
        assert result['inserted'] == 0
        assert result['deleted'] == 2
        assert mock_session.post.call_args.kwargs['json'] == []

    def test_sync_idempotent_retry_on_failure(self, mock_session):
        mock_delete = Mock()
        mock_delete.status_code = 200
        mock_delete.json.return_value = {'deleted': 0}

        mock_session.delete.return_value = mock_delete

        # First call raises, second succeeds
        mock_post = Mock()
        mock_post.status_code = 200
        mock_post.json.return_value = {'deleted': 0, 'inserted': 1}

        def side_effect(*args, **kwargs):
            if not hasattr(side_effect, 'called'):
                side_effect.called = True
                raise requests.Timeout("Timeout")
            return mock_post

        mock_session.post.side_effect = side_effect

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        samples = [{'Folio': 100001, 'ClientId': 101, 'PatientId': 1, 'ExamId': 1,
                   'ExamName': 'Glucose', 'CreatedAt': pd.NaT, 'ReceivedAt': '2024-01-15T12:00:00',
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

    def test_delete_partition_fails_when_route_is_not_found(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.delete.return_value = mock_response

        client = LIMSApiClient.__new__(LIMSApiClient)
        client.base_url = "http://localhost:8080"
        client.api_key = "test_key"
        client.session = mock_session

        with pytest.raises(RuntimeError, match='HTTP 404'):
            client.delete_partition_samples('2024-01-15')

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
        assert call_args.kwargs['params'] == {
            'partitionDate': '2024-01-15', 'clientId': 101
        }


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


class TestExamPartitionContract:
    @pytest.fixture
    def exam(self):
        return {
            'Folio': '100002', 'ClientId': '101', 'PatientId': '387',
            'ExamId': '168', 'ExamName': 'Glucose',
            'CreatedAt': '20/03/2023 12:00:00 AM',
            'ReceivedAt': '20/03/2023 01:18:00 AM',
            'ProcessedAt': '', 'ValidatedAt': '',
            'Location': 'Branch C', 'Outsourcer': '', 'Priority': 'Stat',
            'BirthDate': '21/11/1979'
        }

    def test_mock_lims_dates_become_hub_iso_dates(self, api_client_with_mock, exam):
        converted = api_client_with_mock._convert_exam_format(exam)

        assert converted['receivedAt'] == '2023-03-20T01:18:00'
        assert converted['createdAt'] == '2023-03-20T00:00:00'
        assert converted['birthDate'] == '1979-11-21'
        assert converted['validatedAt'] is None

    def test_mock_lims_localized_date_separator(self, api_client_with_mock, exam):
        localized = dict(exam, ReceivedAt='20-03-2023 01:24:00 AM',
                         BirthDate='15-01-1985')

        converted = api_client_with_mock._convert_exam_format(localized)

        assert converted['receivedAt'] == '2023-03-20T01:24:00'
        assert converted['birthDate'] == '1985-01-15'

    def test_partition_selection_uses_received_date(self, api_client_with_mock, exam):
        prior = dict(exam, Folio='100003', ReceivedAt='19/03/2023 09:32:00 PM')

        assert api_client_with_mock.exams_for_partition(
            [exam, prior], '2023-03-20') == [exam]

    def test_missing_received_date_rejects_batch(self, api_client_with_mock, exam):
        with pytest.raises(ValueError, match='ReceivedAt'):
            api_client_with_mock.exams_for_partition(
                [dict(exam, ReceivedAt='')], '2023-03-20')

    def test_rejected_partition_does_not_fall_back_to_separate_writes(self, api_client_with_mock, exam):
        api_client_with_mock.session.post.return_value.status_code = 400

        with pytest.raises(RuntimeError, match='HTTP 400'):
            api_client_with_mock.sync_exams_idempotent([exam], '2023-03-20')

        assert api_client_with_mock.session.post.call_count == 1
        assert api_client_with_mock.session.post.call_args.kwargs['params'] == {
            'partitionDate': '2023-03-20'
        }
        api_client_with_mock.session.delete.assert_not_called()

    def test_malformed_exam_is_rejected_before_request(self, api_client_with_mock, exam):
        with pytest.raises(ValueError):
            api_client_with_mock.sync_exams_idempotent(
                [dict(exam, Folio='not-a-number')], '2023-03-20')

        api_client_with_mock.session.post.assert_not_called()

    def test_failed_batch_save_is_raised_after_retries(self, api_client_with_mock, exam):
        api_client_with_mock.session.post.return_value.status_code = 503

        with patch('lims_etl.api_client.time.sleep'):
            with pytest.raises(RuntimeError, match='HTTP 503'):
                api_client_with_mock.sync_exams_idempotent([exam], '2023-03-20')

        assert api_client_with_mock.session.post.call_count == 3

    def test_rejected_post_is_not_retried(self, api_client_with_mock, exam):
        api_client_with_mock.session.post.return_value.status_code = 400

        with pytest.raises(RuntimeError, match='HTTP 400'):
            api_client_with_mock.sync_exams_idempotent([exam], '2023-03-20')

        assert api_client_with_mock.session.post.call_count == 1

    def test_atomic_response_reports_complete_replacement(self, api_client_with_mock, exam):
        api_client_with_mock.session.post.return_value.json.return_value = {
            'deleted': 2, 'inserted': 1
        }

        result = api_client_with_mock.sync_exams_idempotent([exam], '2023-03-20')

        assert result['inserted'] == 1
        assert result['deleted'] == 2
        assert result['failed'] == 0

    def test_client_filter_is_sent_with_batch(self, api_client_with_mock, exam):
        api_client_with_mock.sync_exams_idempotent([exam], '2023-03-20', client_id=101)

        assert api_client_with_mock.session.post.call_args.kwargs['params'] == {
            'partitionDate': '2023-03-20', 'clientId': 101
        }
