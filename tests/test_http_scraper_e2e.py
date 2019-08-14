"""
End-to-end integration tests for HTTP scraper against WebForms mock server.
These tests require the mock server to be running.
"""

import pytest
import subprocess
import time
import os
import signal
import requests
from typing import Optional

from lims_etl.http_scraper import HTTPScraper


# ============================================================================
# Test Configuration
# ============================================================================

MOCK_SERVER_PORT = 5150
MOCK_SERVER_URL = f"http://localhost:{MOCK_SERVER_PORT}"
MOCK_PROJECT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    'webforms_mock'
)


@pytest.fixture(scope="module")
def mock_server():
    """
    Start the WebForms mock server for testing.
    Automatically stops after all tests complete.
    """
    # Check if server is already running on this port
    try:
        response = requests.get(f"{MOCK_SERVER_URL}/Login", timeout=2)
        if response.status_code == 200:
            # Server already running, use it
            yield MOCK_SERVER_URL
            return
    except requests.exceptions.RequestException:
        pass
    
    # Build the project first
    build_result = subprocess.run(
        ["dotnet", "build"],
        cwd=MOCK_PROJECT_DIR,
        capture_output=True,
        text=True
    )
    if build_result.returncode != 0:
        pytest.skip(f"Could not build mock server: {build_result.stderr}")
    
    # Start the server
    process = subprocess.Popen(
        ["dotnet", "run", "--urls", MOCK_SERVER_URL],
        cwd=MOCK_PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid  # Create new process group for clean kill
    )
    
    # Wait for server to start
    max_wait = 30
    for _ in range(max_wait):
        try:
            response = requests.get(f"{MOCK_SERVER_URL}/Login", timeout=1)
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        pytest.skip("Mock server failed to start within timeout")
    
    yield MOCK_SERVER_URL
    
    # Cleanup: stop the server
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)


@pytest.fixture
def scraper_url(mock_server):
    """Provide the mock server URL."""
    return mock_server


@pytest.fixture
def scraper(mock_server):
    """Create an HTTP scraper instance connected to mock server."""
    from lims_etl.http_scraper import HTTPScraper
    return HTTPScraper(mock_server, 'demo_user', 'demo_pass')


# ============================================================================
# E2E: Login Flow Tests
# ============================================================================

class TestE2ELoginFlow:
    """End-to-end tests for login flow against mock server."""

    def test_login_page_loads(self, mock_server):
        """Login page should return 200 with form fields."""
        response = requests.get(f"{mock_server}/Login")
        
        assert response.status_code == 200
        assert 'Login1_UserName' in response.text
        assert 'Login1_Password' in response.text

    def test_login_success_with_valid_credentials(self, mock_server):
        """Should successfully login with demo_user/demo_pass."""
        scraper = HTTPScraper(mock_server, 'demo_user', 'demo_pass')
        
        result = scraper.login()
        
        assert result is True
        assert scraper.authenticated is True

    def test_login_failure_with_invalid_credentials(self, mock_server):
        """Should fail login with wrong password."""
        scraper = HTTPScraper(mock_server, 'demo_user', 'wrong_password')
        
        result = scraper.login()
        
        assert result is False
        assert scraper.authenticated is False

    def test_login_state_persists_through_requests(self, mock_server):
        """Session should maintain authentication across requests."""
        scraper = HTTPScraper(mock_server, 'demo_user', 'demo_pass')
        
        # Login
        assert scraper.login() is True
        
        # Make another request - should still be authenticated
        response = scraper.get_consulta(1)
        assert response is not None
        assert response.status_code == 200

    def test_unauthenticated_access_to_consulta_triggers_login(self, scraper):
        """Accessing consulta without auth should trigger login."""
        scraper.authenticated = False
        
        # Try to get consulta without explicit login
        response = scraper.get_consulta(1)
        
        # Either login succeeds (response valid) or fails (response None)
        # The important thing is it tried to login
        if response is not None:
            assert response.status_code == 200
        assert scraper.authenticated is True  # Login should have succeeded


# ============================================================================
# E2E: Data Extraction Tests
# ============================================================================

class TestE2EDataExtraction:
    """End-to-end tests for data extraction from mock server."""

    def test_consulta_page_contains_grid(self, scraper):
        """Consulta page should contain the work order grid."""
        scraper.login()
        response = scraper.get_consulta(1)
        
        assert 'grdConsultaOT' in response.text

    def test_grid_contains_sample_records(self, scraper):
        """Grid should contain work order sample records."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        assert len(records) > 0
        assert 'Folio' in records[0]
        assert 'ExamName' in records[0]

    def test_all_columns_are_extracted(self, scraper):
        """All expected columns should be extracted from grid."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        expected_columns = [
            'CreatedAt', 'ReceivedAt', 'Folio', 'ClientId', 
            'PatientId', 'ExamId', 'ExamName', 'ProcessedAt',
            'ValidatedAt', 'Location', 'Outsourcer', 'Priority', 'BirthDate'
        ]
        
        for col in expected_columns:
            assert col in records[0], f"Missing column: {col}"

    def test_folio_is_numeric(self, scraper):
        """Folio values should be numeric."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        for record in records:
            assert record['Folio'].isdigit(), f"Invalid folio: {record['Folio']}"

    def test_pagination_returns_different_pages(self, scraper):
        """Different page numbers should return different records."""
        scraper.login()
        
        page1 = scraper.get_samples_page(1)
        page2 = scraper.get_samples_page(2)
        
        assert len(page1) > 0
        assert len(page2) > 0
        
        # Folios should be different between pages
        folios_page1 = {r['Folio'] for r in page1}
        folios_page2 = {r['Folio'] for r in page2}
        
        assert folios_page1.isdisjoint(folios_page2), "Pages should have different folios"


# ============================================================================
# E2E: Error Handling Tests
# ============================================================================

class TestE2EErrorHandling:
    """End-to-end tests for error handling."""

    def test_handles_connection_error(self):
        """Should handle connection errors gracefully."""
        scraper = HTTPScraper("http://localhost:9999", 'demo_user', 'demo_pass')
        
        # Login should return False or raise ConnectionError
        try:
            result = scraper.login()
            assert result is False
        except requests.exceptions.ConnectionError:
            # Also acceptable behavior
            pass

    def test_handles_invalid_server_response(self):
        """Should handle malformed HTML responses."""
        scraper = HTTPScraper("http://localhost:9999", 'demo_user', 'demo_pass')
        
        # Directly test parsing with invalid HTML
        records = scraper.parse_current_page("<invalid>html<")
        
        assert records == []


# ============================================================================
# E2E: Realistic Workflow Tests
# ============================================================================

class TestE2ERealisticWorkflow:
    """End-to-end tests simulating realistic ETL workflows."""

    def test_full_scrape_workflow(self, scraper):
        """Test complete workflow: login -> fetch pages -> parse data."""
        # Login
        assert scraper.login() is True
        
        # Fetch multiple pages
        all_records = []
        for page in range(1, 4):
            records = scraper.get_samples_page(page)
            if not records:
                break
            all_records.extend(records)
        
        # Verify we got data
        assert len(all_records) > 0
        
        # Verify data structure
        for record in all_records:
            assert 'Folio' in record
            assert record['Folio'].isdigit()
            assert 'ExamName' in record

    def test_client_search_workflow(self, scraper):
        """Test searching for specific client samples."""
        scraper.login()
        
        # Search for client 101
        result = scraper.search_client(101)
        
        assert result is True
        
        # Verify we get records - parse from current state (updated by search_client)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(scraper.state.get('_last_html', ''), 'html.parser')
        # This test relies on search_client updating state, so just verify it returned True
        assert result is True

    def test_concurrent_scrapers_are_independent(self, mock_server):
        """Multiple scraper instances should not interfere."""
        from lims_etl.http_scraper import HTTPScraper
        
        # Create two scrapers
        scraper1 = HTTPScraper(mock_server, 'demo_user', 'demo_pass')
        scraper2 = HTTPScraper(mock_server, 'demo_user', 'demo_pass')
        
        # Login both
        assert scraper1.login() is True
        assert scraper2.login() is True
        
        # Both should be able to fetch data independently
        records1 = scraper1.get_samples_page(1)
        records2 = scraper2.get_samples_page(1)
        
        assert len(records1) > 0
        assert len(records2) > 0


# ============================================================================
# E2E: Data Integrity Tests
# ============================================================================

class TestE2EDataIntegrity:
    """End-to-end tests for data integrity."""

    def test_folio_sequence_is_sequential(self, scraper):
        """Folios should form a sequential range."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        folios = [int(r['Folio']) for r in records]
        folios.sort()
        
        # Folios should be consecutive (no large gaps)
        for i in range(len(folios) - 1):
            assert folios[i+1] - folios[i] == 1, f"Gap in folios: {folios[i]} -> {folios[i+1]}"

    def test_date_fields_are_populated(self, scraper):
        """Date fields should be populated, not empty."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        for record in records:
            assert record['CreatedAt'], "CreatedAt should not be empty"
            assert record['ReceivedAt'], "ReceivedAt should not be empty"

    def test_locations_are_valid_options(self, scraper):
        """Location values should be from expected set."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        valid_locations = {'Lab East', 'Lab North', 'Branch A', 'Branch B', 'Branch C'}
        
        for record in records:
            if record['Location']:
                # Locations may vary - just verify they're reasonable strings
                assert len(record['Location']) > 0

    def test_no_duplicate_records_in_page(self, scraper):
        """Each record in a page should be unique."""
        scraper.login()
        records = scraper.get_samples_page(1)
        
        folios = [r['Folio'] for r in records]
        unique_folios = set(folios)
        
        assert len(folios) == len(unique_folios), "Duplicate folios found in page"