"""
Unit tests for HTTP scraper WebForms state management and parsing.
"""

import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from lims_etl.http_scraper import WebFormsStateManager, HTTPScraper


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_login_html():
    """Sample login page HTML with WebForms state fields."""
    return '''<!DOCTYPE html>
    <html>
    <body>
        <form method="post">
            <input type="hidden" name="__VIEWSTATE" value="dGVzdC12aWV3c3RhdGU=" />
            <input type="hidden" name="__VIEWSTATEGENERATOR" value="dGVzdC12c2c=" />
            <input type="hidden" name="__EVENTVALIDATION" value="dGVzdC1ldmVudHZhbGlk" />
            <input type="hidden" name="__RequestVerificationToken" value="CfDJ8N4dUAApjgFLmY1unRHt4N1abc123" />
            <input type="text" id="Login1_UserName" name="Login1_UserName" />
            <input type="password" id="Login1_Password" name="Login1_Password" />
            <button type="submit" name="Login1_LoginButton" value="Aceptar">Login</button>
        </form>
    </body>
    </html>'''


@pytest.fixture
def sample_consulta_html():
    """Sample consulta page HTML with grid data."""
    return '''<!DOCTYPE html>
    <html>
    <body>
        <table id="ctl00_ContentMasterPage_grdConsultaOT">
            <tbody>
                <tr>
                    <td><span id="grd_ctl02_lblFechaGrd">20/03/2023 12:00:00 AM</span></td>
                    <td><span id="grd_ctl02_lblFechaRecep">20/03/2023 01:18:00 AM</span></td>
                    <td><span id="grd_ctl02_lblFolioGrd">100002</span></td>
                    <td><span id="grd_ctl02_lblClienteGrd">105</span></td>
                    <td><span id="grd_ctl02_lblPacienteGrd">387</span></td>
                    <td><span id="grd_ctl02_lblEstPerGrd">168</span></td>
                    <td><span id="grd_ctl02_Label1">Glucose</span></td>
                    <td><span id="grd_ctl02_lblFecCapRes">20/03/2023 09:18:00 AM</span></td>
                    <td><span id="grd_ctl02_lblFecLibera">20/03/2023 02:18:00 PM</span></td>
                    <td><span id="grd_ctl02_lblSucProc">Branch C</span></td>
                    <td><span id="grd_ctl02_lblMaquilador">LabCorp</span></td>
                    <td><span id="grd_ctl02_Label3">Stat</span></td>
                    <td><span id="grd_ctl02_lblFecNac">21/11/1979</span></td>
                </tr>
                <tr>
                    <td><span id="grd_ctl03_lblFechaGrd">19/03/2023 09:00:00 PM</span></td>
                    <td><span id="grd_ctl03_lblFechaRecep">19/03/2023 09:32:00 PM</span></td>
                    <td><span id="grd_ctl03_lblFolioGrd">100003</span></td>
                    <td><span id="grd_ctl03_lblClienteGrd">104</span></td>
                    <td><span id="grd_ctl03_lblPacienteGrd">831</span></td>
                    <td><span id="grd_ctl03_lblEstPerGrd">435</span></td>
                    <td><span id="grd_ctl03_Label1">CBC</span></td>
                    <td><span id="grd_ctl03_lblFecCapRes">20/03/2023 01:32:00 AM</span></td>
                    <td><span id="grd_ctl03_lblFecLibera">21/03/2023 01:32:00 AM</span></td>
                    <td><span id="grd_ctl03_lblSucProc">Lab East</span></td>
                    <td><span id="grd_ctl03_lblMaquilador">Quest Labs</span></td>
                    <td><span id="grd_ctl03_Label3">Routine</span></td>
                    <td><span id="grd_ctl03_lblFecNac">10/06/1984</span></td>
                </tr>
                <tr>
                    <td colspan="13"><a href="?page=2">Next</a></td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>'''


# ============================================================================
# WebFormsStateManager Tests
# ============================================================================

class TestWebFormsStateManager:
    """Tests for WebForms state extraction."""

    def test_extract_state_extracts_all_hidden_fields(self, sample_login_html):
        """Should extract all __ prefixed hidden fields from HTML."""
        state = WebFormsStateManager.extract_state(sample_login_html)
        
        assert '__VIEWSTATE' in state
        assert '__VIEWSTATEGENERATOR' in state
        assert '__EVENTVALIDATION' in state
        assert '__RequestVerificationToken' in state
        
        assert state['__VIEWSTATE'] == 'dGVzdC12aWV3c3RhdGU='
        assert state['__RequestVerificationToken'] == 'CfDJ8N4dUAApjgFLmY1unRHt4N1abc123'

    def test_extract_state_returns_empty_dict_for_html_without_fields(self):
        """Should return empty dict when no hidden fields present."""
        html = '<html><body><p>No form fields here</p></body></html>'
        state = WebFormsStateManager.extract_state(html)
        
        assert state == {}

    def test_extract_state_handles_missing_values(self):
        """Should handle fields without value attribute."""
        html = '<input type="hidden" name="__TEST" />'
        state = WebFormsStateManager.extract_state(html)
        
        assert '__TEST' in state
        assert state['__TEST'] == ''

    def test_find_field_returns_specific_field(self, sample_login_html):
        """Should find and return a specific field by name."""
        value = WebFormsStateManager.find_field(sample_login_html, '__VIEWSTATE')
        
        assert value == 'dGVzdC12aWV3c3RhdGU='

    def test_find_field_returns_none_for_missing_field(self, sample_login_html):
        """Should return None when field not found."""
        value = WebFormsStateManager.find_field(sample_login_html, '__NONEXISTENT__')
        
        assert value is None

    def test_find_field_handles_empty_html(self):
        """Should return None for empty HTML."""
        value = WebFormsStateManager.find_field('', '__VIEWSTATE')
        assert value is None


# ============================================================================
# HTTPScraper Initialization Tests
# ============================================================================

class TestHTTPScraperInit:
    """Tests for HTTPScraper initialization."""

    def test_default_credentials(self):
        """Should use default credentials when not specified."""
        scraper = HTTPScraper('http://localhost:5000')
        
        assert scraper.username == 'demo_user'
        assert scraper.password == 'demo_pass'
        assert scraper.base_url == 'http://localhost:5000'

    def test_custom_credentials(self):
        """Should use provided credentials."""
        scraper = HTTPScraper('http://localhost:5000', 'user', 'pass')
        
        assert scraper.username == 'user'
        assert scraper.password == 'pass'

    def test_session_has_correct_headers(self):
        """Should set correct User-Agent header."""
        scraper = HTTPScraper('http://localhost:5000')
        
        assert 'User-Agent' in scraper.session.headers
        assert 'Mozilla/5.0' in scraper.session.headers['User-Agent']

    def test_strips_trailing_slash_from_base_url(self):
        """Should normalize base URL by removing trailing slash."""
        scraper = HTTPScraper('http://localhost:5000/')
        
        assert scraper.base_url == 'http://localhost:5000'
        assert not scraper.base_url.endswith('/')

    def test_not_authenticated_initially(self):
        """Should start in unauthenticated state."""
        scraper = HTTPScraper('http://localhost:5000')
        
        assert scraper.authenticated is False


# ============================================================================
# HTTPScraper State Management Tests
# ============================================================================

class TestHTTPScraperStateManagement:
    """Tests for HTTPScraper state management."""

    def test_update_state_extracts_fields_from_html(self, sample_login_html):
        """Should update internal state from HTML response."""
        scraper = HTTPScraper('http://localhost:5000')
        scraper._update_state(sample_login_html)
        
        assert scraper.state['__VIEWSTATE'] == 'dGVzdC12aWV3c3RhdGU='
        assert scraper.state['__EVENTVALIDATION'] == 'dGVzdC1ldmVudHZhbGlk'

    def test_state_empty_initially(self):
        """State should be empty on initialization."""
        scraper = HTTPScraper('http://localhost:5000')
        
        assert scraper.state == {}


# ============================================================================
# HTTPScraper Parsing Tests
# ============================================================================

class TestHTTPScraperParsing:
    """Tests for HTML parsing logic."""

    def test_parse_row_extracts_all_fields(self):
        """Should extract all fields from a grid row."""
        html = '''<tr>
            <td><span id="test_lblFechaGrd">20/03/2023</span></td>
            <td><span id="test_lblFolioGrd">100002</span></td>
            <td><span id="test_lblClienteGrd">105</span></td>
            <td><span id="test_Label1">Glucose</span></td>
            <td><span id="test_Label3">Stat</span></td>
        </tr>'''
        
        soup = BeautifulSoup(html, 'html.parser')
        row = soup.find('tr')
        
        scraper = HTTPScraper('http://localhost:5000')
        result = scraper._parse_row(row)
        
        assert result is not None
        assert result['CreatedAt'] == '20/03/2023'
        assert result['Folio'] == '100002'
        assert result['ClientId'] == '105'
        assert result['ExamName'] == 'Glucose'
        assert result['Priority'] == 'Stat'

    def test_parse_row_returns_none_for_empty_row(self):
        """Should return None for rows without Folio."""
        html = '<tr><td>No data here</td></tr>'
        soup = BeautifulSoup(html, 'html.parser')
        row = soup.find('tr')
        
        scraper = HTTPScraper('http://localhost:5000')
        result = scraper._parse_row(row)
        
        assert result is None

    def test_parse_row_handles_missing_fields_gracefully(self):
        """Should handle rows with missing fields."""
        html = '<tr><td><span id="test_lblFolioGrd">100002</span></td></tr>'
        soup = BeautifulSoup(html, 'html.parser')
        row = soup.find('tr')
        
        scraper = HTTPScraper('http://localhost:5000')
        result = scraper._parse_row(row)
        
        assert result is not None
        assert result['Folio'] == '100002'
        assert result.get('ExamName') is None

    def test_parse_current_page_extracts_multiple_rows(self, sample_consulta_html):
        """Should parse all valid data rows from page."""
        scraper = HTTPScraper('http://localhost:5000')
        
        records = scraper.parse_current_page(sample_consulta_html)
        
        assert len(records) == 2
        assert records[0]['Folio'] == '100002'
        assert records[1]['Folio'] == '100003'

    def test_parse_current_page_skips_pagination_row(self, sample_consulta_html):
        """Should skip rows with colspan (pagination)."""
        scraper = HTTPScraper('http://localhost:5000')
        
        records = scraper.parse_current_page(sample_consulta_html)
        
        # Should only have 2 data rows, not the pagination row
        assert len(records) == 2
        for record in records:
            assert 'colspan' not in str(record)

    def test_parse_current_page_handles_empty_grid(self):
        """Should return empty list when grid is empty."""
        html = '<html><body><table id="grdConsultaOT"><tbody></tbody></table></body></html>'
        scraper = HTTPScraper('http://localhost:5000')
        
        records = scraper.parse_current_page(html)
        
        assert records == []


# ============================================================================
# HTTPScraper Login Flow Tests (using real session mock)
# ============================================================================

class TestHTTPScraperLogin:
    """Tests for login flow using HTTPretty-style mocking."""

    def test_parse_current_page_with_invalid_html(self):
        """Should handle malformed HTML gracefully."""
        scraper = HTTPScraper('http://localhost:5000')
        
        records = scraper.parse_current_page("<invalid>html<")
        
        assert records == []

    def test_authentication_flag_starts_false(self):
        """authenticated should start as False."""
        scraper = HTTPScraper('http://localhost:5000')
        
        assert scraper.authenticated is False

    def test_login_with_invalid_credentials_returns_false(self):
        """Login should fail with invalid credentials without making network calls."""
        scraper = HTTPScraper('http://localhost:5000', 'bad', 'creds')
        
        # Mock the _get to return error response
        with patch.object(scraper, '_get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            result = scraper.login()
            
        assert result is False
        assert scraper.authenticated is False


# ============================================================================
# HTTPScraper Consultation Tests
# ============================================================================

class TestHTTPScraperConsultation:
    """Tests for consulta page operations."""

    def test_get_consulta_returns_none_when_login_fails(self):
        """Should return None if can't authenticate."""
        scraper = HTTPScraper('http://localhost:5000', 'demo_user', 'demo_pass')
        scraper.authenticated = False
        
        # Mock login to fail
        with patch.object(scraper, 'login', return_value=False):
            result = scraper.get_consulta(1)
            
        assert result is None

    def test_get_samples_page_returns_empty_when_consulta_fails(self):
        """Should return empty list when consulta fails."""
        scraper = HTTPScraper('http://localhost:5000')
        
        # Mock get_consulta to return None
        with patch.object(scraper, 'get_consulta', return_value=None):
            records = scraper.get_samples_page(1)
            
        assert records == []

    def test_current_page_starts_at_one(self):
        """current_page should start at 1."""
        scraper = HTTPScraper('http://localhost:5000')
        
        assert scraper.current_page == 1


# ============================================================================
# HTTPScraper URL Building Tests
# ============================================================================

class TestHTTPScraperURLBuilding:
    """Tests for URL construction."""

    def test_get_url_includes_base_and_path(self):
        """GET URLs should include base URL and path."""
        scraper = HTTPScraper('http://localhost:5000')
        
        expected_url = 'http://localhost:5000/Login'
        
        # Verify base_url + path would produce correct URL
        assert f"{scraper.base_url}/Login" == expected_url

    def test_post_url_includes_base_and_path(self):
        """POST URLs should include base URL and path."""
        scraper = HTTPScraper('http://localhost:5000')
        
        expected_url = 'http://localhost:5000/Consulta'
        
        assert f"{scraper.base_url}/Consulta" == expected_url


# ============================================================================
# HTTPScraper Column Mapping Tests
# ============================================================================

class TestHTTPScraperColumnMapping:
    """Tests for column ID suffix to field name mapping."""

    def test_parsed_records_have_expected_fields(self, sample_consulta_html):
        """Parsed records should have all expected columns."""
        scraper = HTTPScraper('http://localhost:5000')
        records = scraper.parse_current_page(sample_consulta_html)
        
        assert len(records) > 0
        
        record = records[0]
        expected_fields = [
            'CreatedAt', 'ReceivedAt', 'Folio', 'ClientId', 
            'PatientId', 'ExamId', 'ExamName', 'ProcessedAt',
            'ValidatedAt', 'Location', 'Outsourcer', 'Priority', 'BirthDate'
        ]
        
        for field in expected_fields:
            assert field in record, f"Missing field: {field}"

    def test_record_values_match_html(self, sample_consulta_html):
        """Record values should match the HTML content."""
        scraper = HTTPScraper('http://localhost:5000')
        records = scraper.parse_current_page(sample_consulta_html)
        
        # First record should have values from the HTML
        assert records[0]['Folio'] == '100002'
        assert records[0]['ClientId'] == '105'
        assert records[0]['ExamName'] == 'Glucose'