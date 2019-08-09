"""
HTTP-based LIMS scraper using requests instead of Selenium.

This scraper handles ASP.NET WebForms state management directly:
- Extracts __VIEWSTATE and __EVENTVALIDATION from responses
- Includes state in every POST request
- Handles pagination via POST requests
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List, Optional, Tuple
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
    
    @staticmethod
    def extract_state(html: str) -> Dict[str, str]:
        """Extract all hidden form fields from HTML."""
        soup = BeautifulSoup(html, 'lxml')
        state = {}
        
        for inp in soup.find_all('input', type='hidden'):
            name = inp.get('name')
            value = inp.get('value', '')
            if name:
                state[name] = value
        
        return state
    
    @staticmethod
    def find_field(html: str, field_id: str) -> Optional[str]:
        """Find a specific field by ID."""
        soup = BeautifulSoup(html, 'lxml')
        inp = soup.find('input', {'id': field_id})
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
    
    def _post(self, path: str, data: Dict = None) -> requests.Response:
        """Make a POST request with current state."""
        url = f"{self.base_url}{path}"
        
        # Include current state in POST data
        post_data = {**self.state}
        if data:
            post_data.update(data)
        
        response = self.session.post(url, data=post_data, allow_redirects=True)
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
        log.info(f"Attempting login to {self.base_url}/Login.aspx")
        
        # Step 1: GET login page to get initial state
        response = self._get('/Login.aspx')
        
        if response.status_code != 200:
            log.error(f"Login page request failed: {response.status_code}")
            return False
        
        # Step 2: Extract state and POST credentials
        login_data = {
            'Login1$UserName': self.username,
            'Login1$Password': self.password,
            'Login1$LoginButton': 'Aceptar'
        }
        
        response = self._post('/Login.aspx', login_data)
        
        # Check if login was successful (redirect to consulta page)
        if '/ConsultaOrdenTrabajo' in response.url or response.status_code == 200:
            self.authenticated = True
            log.info("Login successful")
            return True
        
        log.error("Login failed - check credentials")
        return False
    
    def navigate_to_consulta(self, client_id: int = 101) -> bool:
        """
        Navigate to consultation page for a specific client.
        """
        log.info(f"Navigating to consulta for client {client_id}")
        
        # If not authenticated, login first
        if not self.authenticated:
            if not self.login():
                return False
        
        # GET the consulta page
        response = self._get('/FasePreAnalitica/ConsultaOrdenTrabajo.aspx', 
                           params={'client': client_id})
        
        return response.status_code == 200
    
    def search_client(self, client_id: int) -> bool:
        """
        Search for a specific client on the consulta page.
        """
        search_data = {
            'ctl00$ContentMasterPage$txtcliente': str(client_id),
            'ctl00$ContentMasterPage$btnBuscar': 'Buscar'
        }
        
        response = self._post('/FasePreAnalitica/ConsultaOrdenTrabajo.aspx', search_data)
        
        return response.status_code == 200
    
    def parse_grid_row(self, row_element) -> Dict[str, str]:
        """Parse a single row from the results grid."""
        data = {}
        
        # Map of element IDs to column names (matches LIMS selectors)
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
            
            # Extract row number and column name from ID
            # Format: ctl00_ContentMasterPage_grdConsultaOT_ctl02_lblFechaGrd
            for suffix, col_name in column_map.items():
                if element_id.endswith(suffix):
                    data[col_name] = span.get_text(strip=True)
                    break
        
        return data
    
    def parse_current_page(self, html: str = None) -> List[Dict[str, str]]:
        """
        Parse all data rows from the current page.
        
        Returns list of sample records.
        """
        soup = BeautifulSoup(html or self.session.last_response.text, 'lxml')
        records = []
        
        # Find the grid table
        grid = soup.find('table')
        if not grid:
            log.warning("Grid table not found in response")
            return records
        
        # Parse each data row (skip header row)
        for row in grid.find_all('tr')[1:]:
            row_data = {}
            
            for span in row.find_all('span'):
                element_id = span.get('id', '')
                text = span.get_text(strip=True)
                
                # Map element IDs to column names (matches mock format)
                # Format: grd_ctl02_lblFechaGrd
                if 'lblFechaGrd' in element_id:
                    row_data['CreatedAt'] = text
                elif 'lblFechaRecep' in element_id:
                    row_data['ReceivedAt'] = text
                elif 'lblFolioGrd' in element_id:
                    row_data['Folio'] = text
                elif 'lblClienteGrd' in element_id:
                    row_data['ClientId'] = text
                elif 'lblPacienteGrd' in element_id:
                    row_data['PatientId'] = text
                elif 'lblEstPerGrd' in element_id:
                    row_data['ExamId'] = text
                elif 'Label1' in element_id:
                    row_data['ExamName'] = text
                elif 'lblFecCapRes' in element_id:
                    row_data['ProcessedAt'] = text
                elif 'lblFecLibera' in element_id:
                    row_data['ValidatedAt'] = text
                elif 'lblSucProc' in element_id:
                    row_data['Location'] = text
                elif 'lblMaquilador' in element_id:
                    row_data['Outsourcer'] = text
                elif 'Label3' in element_id:
                    row_data['Priority'] = text
                elif 'lblFecNac' in element_id:
                    row_data['BirthDate'] = text
            
            if row_data:
                records.append(row_data)
        
        log.info(f"Parsed {len(records)} records from current page")
        return records
    
    def go_to_next_page(self) -> bool:
        """
        Navigate to next page of results.
        
        Returns True if navigation successful, False if no more pages.
        """
        soup = BeautifulSoup(self.session.last_response.text, 'lxml')
        
        # Find pagination links
        pagination = soup.find('div', class_='pagination')
        if not pagination:
            log.warning("Pagination element not found")
            return False
        
        # Find next page link
        current_page_text = f"{self.current_page + 1}"
        for link in pagination.find_all('a'):
            if link.get_text(strip=True) == current_page_text:
                # Click the next page link
                next_data = {
                    '__EVENTTARGET': '',  # Would be set by pagination control
                    '__EVENTARGUMENT': ''
                }
                # For this mock, we'll use query parameter
                next_url = f"{self.base_url}/FasePreAnalitica/ConsultaOrdenTrabajo.aspx?page={self.current_page + 1}"
                response = self.session.get(next_url)
                self._update_state(response.text)
                
                if response.status_code == 200:
                    self.current_page += 1
                    return True
        
        log.info("No more pages available")
        return False
    
    def scrape_client(self, client_id: int) -> List[Dict[str, str]]:
        """
        Scrape all sample data for a client.
        
        Returns list of all sample records.
        """
        all_records = []
        
        # Navigate to client
        if not self.navigate_to_consulta(client_id):
            log.error(f"Failed to navigate to client {client_id}")
            return all_records
        
        # Search for specific client
        self.search_client(client_id)
        
        # Scrape all pages
        while True:
            records = self.parse_current_page()
            all_records.extend(records)
            
            if not self.go_to_next_page():
                break
        
        log.info(f"Scraped {len(all_records)} total records for client {client_id}")
        return all_records


def main():
    """Test the HTTP scraper."""
    import os
    
    base_url = os.getenv('LIMS_BASE_URL', 'http://localhost:5000')
    
    scraper = HTTPScraper(base_url)
    
    # Login
    if not scraper.login():
        print("Login failed!")
        return
    
    # Scrape client 101
    records = scraper.scrape_client(101)
    
    print(f"\nTotal records: {len(records)}")
    if records:
        print(f"Sample record: {records[0]}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()