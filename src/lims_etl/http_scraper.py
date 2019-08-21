"""
HTTP-based LIMS scraper using requests instead of Selenium.

This scraper handles ASP.NET WebForms state management directly:
- Extracts __VIEWSTATE and __EVENTVALIDATION from responses
- Includes state in every POST request
- Handles pagination via query parameters
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)


class WebFormsStateManager:
    """Manages ASP.NET WebForms state variables."""
    
    HIDDEN_FIELDS = [
        '__VIEWSTATE',
        '__VIEWSTATEGENERATOR', 
        '__VIEWSTATEENCRYPTED',
        '__EVENTVALIDATION',
        '__EVENTTARGET',
        '__EVENTARGUMENT',
        '__LASTFOCUS'
    ]
    
    # ASP.NET Core Antiforgery token
    ANTIFORGERY_TOKEN = '__RequestVerificationToken'
    
    @staticmethod
    def extract_state(html: str) -> Dict[str, str]:
        """Extract all hidden form fields from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        state = {}
        
        for inp in soup.find_all('input', type='hidden'):
            name = inp.get('name')
            value = inp.get('value', '')
            if name and name.startswith('__'):
                state[name] = value
        
        return state
    
    @staticmethod
    def find_field(html: str, field_name: str) -> Optional[str]:
        """Find a specific field by name."""
        soup = BeautifulSoup(html, 'html.parser')
        inp = soup.find('input', {'name': field_name})
        return inp.get('value') if inp else None


class HTTPScraper:
    """
    HTTP-based scraper for ASP.NET WebForms LIMS.
    
    Handles the stateful nature of WebForms by extracting
    and reusing __VIEWSTATE, __EVENTVALIDATION from each response.
    """
    
    def __init__(self, base_url: str, username: str = 'demo_user', 
                 password: str = 'demo_pass'):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        self.state = {}
        self.authenticated = False
        self.current_page = 1
    
    def _update_state(self, html: str):
        """Update internal state from HTML response."""
        self.state = WebFormsStateManager.extract_state(html)
    
    def _post(self, path: str, data: Dict = None, allow_redirects: bool = True) -> requests.Response:
        """Make a POST request with current state."""
        url = f"{self.base_url}{path}"
        
        # Build POST data with current state
        post_data = {k: v for k, v in self.state.items() if v}
        if data:
            post_data.update(data)
        
        response = self.session.post(url, data=post_data, allow_redirects=allow_redirects)
        self._update_state(response.text)
        
        return response
    
    def _get(self, path: str, params: Dict = None) -> requests.Response:
        """Make a GET request."""
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params, allow_redirects=True)
        self._update_state(response.text)
        
        return response
    
    def login(self) -> bool:
        """
        Login to LIMS with credentials.
        
        Returns True if authentication successful.
        """
        log.info(f"Attempting login to {self.base_url}/Login")
        
        # Step 1: GET login page to get initial state
        response = self._get('/Login')
        
        if response.status_code != 200:
            log.error(f"Login page request failed: {response.status_code}")
            return False
        
        # Step 2: Extract state and POST credentials
        # Field names match the mock: Login1_UserName, Login1_Password, etc.
        login_data = {
            'Login1_UserName': self.username,
            'Login1_Password': self.password,
            'Login1_LoginButton': 'Aceptar'
        }
        
        response = self._post('/Login', login_data, allow_redirects=True)
        
        # Check if login was successful (redirect to consulta page)
        if response.status_code == 302 or '/Consulta' in response.url:
            self.authenticated = True
            log.info("Login successful")
            return True
        
        # Also check if we're on Consulta page now
        if '/Consulta' in response.text or 'grdConsultaOT' in response.text:
            self.authenticated = True
            log.info("Login successful (via content check)")
            return True
        
        log.error("Login failed - check credentials")
        return False
    
    def get_consulta(self, page: int = 1) -> requests.Response:
        """
        GET the consulta page.
        
        Args:
            page: Page number (1-indexed).
            
        Returns:
            Response object if successful, None otherwise.
        """
        if not self.authenticated:
            if not self.login():
                return None
        
        params = {'page': page} if page > 1 else None
        response = self._get('/Consulta', params)
        
        if response.status_code != 200:
            log.error(f"Consulta request failed: {response.status_code}")
            return None
            
        return response
    
    def search_client(self, client_id: int) -> bool:
        """
        Search for a specific client on the consulta page.
        
        Args:
            client_id: Client ID to search for.
            
        Returns:
            True if search performed successfully.
        """
        search_data = {
            'ctl00_ContentMasterPage_txtcliente': str(client_id),
            'ctl00_ContentMasterPage_btnBuscar': 'Buscar'
        }
        
        response = self._post('/Consulta', search_data)
        return response.status_code == 200
    
    def parse_current_page(self, html: str = None) -> List[Dict[str, str]]:
        """
        Parse all data rows from the current page.
        
        Returns list of sample records.
        """
        soup = BeautifulSoup(html, 'html.parser')
        records = []
        
        # Find the grid table by ID pattern
        grid = soup.find('table', {'id': lambda x: x and 'grdConsultaOT' in x})
        if not grid:
            log.warning("Grid table not found in response")
            return records
        
        # Get all rows in tbody
        tbody = grid.find('tbody')
        if not tbody:
            log.warning("Grid tbody not found")
            return records
        
        # Parse each data row
        for row in tbody.find_all('tr'):
            # Skip pagination row (has colspan)
            if row.find('td', {'colspan': '13'}):
                continue
            
            row_data = self._parse_row(row)
            if row_data:
                records.append(row_data)
        
        log.info(f"Parsed {len(records)} records from current page")
        return records
    
    def _parse_row(self, row_element) -> Optional[Dict[str, str]]:
        """Parse a single row from the grid."""
        row_data = {}
        
        # Map of element ID suffix to column name
        column_map = {
            'lblFechaGrd': 'CreatedAt',
            'lblFechaRecep': 'ReceivedAt',
            'lblFolioGrd': 'Folio',
            'lblClienteGrd': 'ClientId',
            'lblPacienteGrd': 'PatientId',
            'lblEstPerGrd': 'ExamId',
            'Label1': 'ExamName',
            'lblFecCapRes': 'ProcessedAt',
            'lblFecLibera': 'ValidatedAt',
            'lblSucProc': 'Location',
            'lblMaquilador': 'Outsourcer',
            'Label3': 'Priority',
            'lblFecNac': 'BirthDate'
        }
        
        for span in row_element.find_all('span'):
            element_id = span.get('id', '')
            text = span.get_text(strip=True)
            
            # Match element ID suffix
            for suffix, col_name in column_map.items():
                if element_id.endswith(suffix):
                    row_data[col_name] = text
                    break
        
        # Only return if we have at least a Folio
        return row_data if row_data.get('Folio') else None
    
    def get_samples_page(self, page: int = 1) -> List[Dict[str, str]]:
        """
        Get all samples from a specific page.
        
        Args:
            page: Page number (1-indexed).
            
        Returns:
            List of sample records.
        """
        response = self.get_consulta(page)
        if not response:
            return []
        
        return self.parse_current_page(response.text)
    
    def scrape_all(self, client_id: int = None) -> List[Dict[str, str]]:
        """
        Scrape all sample data for the configured client.
        
        Args:
            client_id: Optional client ID to search for.
            
        Returns:
            List of all sample records.
        """
        all_records = []
        
        # Login if needed
        if not self.authenticated:
            if not self.login():
                log.error("Failed to login")
                return all_records
        
        # Search for client if specified
        if client_id:
            self.search_client(client_id)
        
        # Scrape first page
        page = 1
        while True:
            records = self.get_samples_page(page)
            if not records:
                break
            
            all_records.extend(records)
            page += 1
            
            # Safety limit (mock has 10 pages)
            if page > 100:
                break
        
        log.info(f"Scraped {len(all_records)} total records")
        return all_records


def main():
    """Test the HTTP scraper against the mock server."""
    import os
    
    base_url = os.getenv('LIMS_BASE_URL', 'http://localhost:5080')
    
    scraper = HTTPScraper(base_url)
    
    # Login
    if not scraper.login():
        print("Login failed!")
        return
    
    # Get first page
    records = scraper.get_samples_page(1)
    
    print(f"\nTotal records on page 1: {len(records)}")
    if records:
        print(f"Sample record: {records[0]}")
        
        # Verify field parsing
        record = records[0]
        print(f"  Folio: {record.get('Folio')}")
        print(f"  ClientId: {record.get('ClientId')}")
        print(f"  ExamName: {record.get('ExamName')}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()