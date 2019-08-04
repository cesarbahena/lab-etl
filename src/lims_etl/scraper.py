#!/usr/bin/env python3
"""
LIMS Sample Tracker ETL Pipeline
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from time import sleep
from datetime import datetime, timedelta
import pandas as pd
import logging
import pathlib
import argparse
from typing import Dict, List, Optional
from .config import LIMSConfig
from .browser import Browser
from .api_client import QuimiOSHubClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('Registro.log'),
        logging.StreamHandler()
    ]
)
reg = logging.getLogger(__name__)

# Map LIMS HTML element IDs to database column names
SELECTOR_TO_COLUMN = {
    '_lblFechaGrd': 'CreatedAt',
    '_lblFechaRecep': 'ReceivedAt',
    '_lblFolioGrd': 'Folio',
    '_lblClienteGrd': 'ClientId',
    '_lblPacienteGrd': 'PatientId',
    '_lblEstPerGrd': 'ExamId',
    '_Label1': 'ExamName',
    '_lblFecCapRes': 'ProcessedAt',
    '_lblFecLibera': 'ValidatedAt',
    '_lblSucProc': 'Location',
    '_lblMaquilador': 'Outsourcer',
    '_Label3': 'Priority',
    '_lblFecNac': 'BirthDate'
}

# Data types for pandas DataFrame (using database column names)
dtypes = {
    'CreatedAt': 'datetime64[ns]',
    'ReceivedAt': 'datetime64[ns]',
    'Folio': 'uint32',
    'ClientId': 'uint16',
    'PatientId': 'uint16',
    'ExamId': 'uint16',
    'ExamName': 'category',
    'ProcessedAt': 'datetime64[ns]',
    'ValidatedAt': 'datetime64[ns]',
    'Location': 'category',
    'Outsourcer': 'category',
    'Priority': 'category',
    'BirthDate': 'datetime64[ns]',
}

cols = list(dtypes.keys())
date_cols = ['CreatedAt', 'ReceivedAt', 'ProcessedAt', 'ValidatedAt', 'BirthDate']



class Scraper:
    """LIMS web scraper"""
    
    def __init__(self, client_id: int, config: LIMSConfig):
        if not isinstance(client_id, int) or client_id <= 0:
            raise ValueError("client_id must be a positive integer")
        self.client = client_id
        self.config = config
        self.browser = Browser(config)
        self.driver: Optional[webdriver.Chrome] = None
        self.data: Dict[str, List] = {col: [] for col in cols}
        self.empty_pages_count = 0
        self.current_page = 1
        
    def __enter__(self):
        """Context manager entry"""
        self.driver = self.browser.__enter__()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures driver cleanup"""
        self.browser.__exit__(exc_type, exc_val, exc_tb)
    
    def login(self) -> bool:
        """Login to LIMS system with error handling"""
        try:
            # Check if already logged in
            self.driver.find_element(By.XPATH, self.config.selectors["LOGIN_SUCCESS_CHECK"])
            reg.info("Already logged in")
            return True
        except Exception:
            try:
                reg.info('Logging into LIMS')
                self.driver.get(self.config.get_login_url())

                # Enter credentials
                self.driver.find_element(By.ID, self.config.selectors["LOGIN_USERNAME_FIELD"]).send_keys(self.config.username)
                self.driver.find_element(By.ID, self.config.selectors["LOGIN_PASSWORD_FIELD"]).send_keys(self.config.password)
                self.driver.find_element(By.ID, self.config.selectors["LOGIN_BUTTON"]).click()

                sleep(self.config.sleep_time * 2)
                reg.info("Login successful")
                return True

            except Exception as e:
                reg.error(f"Login failed: {e}")
                return False
    
    def navigate_to_client(self) -> bool:
        """Navigate to client consultation page"""
        try:
            # Check current client
            try:
                current_client_element = self.driver.find_element(
                    By.XPATH, self.config.selectors["CLIENT_CURRENT_USER_LABEL"]
                )
                current_client = int(current_client_element.text)
                
                if current_client == self.client:
                    reg.info(f'Already viewing client {self.client}')
                    return True
            except Exception:
                pass
            
            # Navigate to consultation page
            reg.info(f'Searching for client {self.client}')
            consulta_path = f'file://{pathlib.Path("consulta.html").resolve()}'
            self.driver.get(consulta_path)
            
            # Enter client ID and search
            client_input = self.driver.find_element(By.ID, self.config.selectors["CLIENT_INPUT_FIELD"])
            client_input.clear()
            client_input.send_keys(str(self.client))
            self.driver.find_element(By.ID, self.config.selectors["CLIENT_SEARCH_BUTTON"]).click()
            
            sleep(self.config.sleep_time * 2)
            reg.info(f'Successfully navigated to client {self.client}')
            return True
            
        except Exception as e:
            reg.error(f"Failed to navigate to client {self.client}: {e}")
            return False
    
    def extract_cell_data(self, row: int, col: str) -> str:
        """Extract data from a specific grid cell"""
        try:
            element_id = f'{self.config.selectors["GRID_ROW_BASE"]}{str(row).zfill(2)}{col}'
            element = self.driver.find_element(By.ID, element_id)
            return element.text
        except Exception as e:
            reg.debug(f"Could not extract data from row {row}, column {col}: {e}")
            return ""
    
    def parse_date(self, row: int, col: str) -> datetime:
        """Parse date from grid cell with error handling"""
        try:
            date_text = self.extract_cell_data(row, col)
            if not date_text:
                return pd.NaT
            
            return datetime.strptime(date_text, '%d/%m/%Y %I:%M:%S %p')
        except Exception as e:
            reg.debug(f"Could not parse date from row {row}, column {col}: {e}")
            return pd.NaT
    
    def parse_birth_date(self, row: int) -> datetime:
        """Parse birth date with simpler format"""
        try:
            date_text = self.extract_cell_data(row, '_lblFecNac')
            if not date_text:
                return pd.NaT
            return datetime.strptime(date_text, '%d/%m/%Y')
        except Exception as e:
            reg.debug(f"Could not parse birth date from row {row}: {e}")
            return pd.NaT

    def scan_page(self) -> int:
        """Scan current page for sample data within date range"""
        samples_found = 0
        # Reverse mapping for getting selectors from database columns
        column_to_selector = {v: k for k, v in SELECTOR_TO_COLUMN.items()}

        # Scan rows 2-11
        for row in range(2, 12):
            try:
                reception_date = self.parse_date(row, '_lblFechaRecep')

                # Check if within date range
                if self.config.start_date > reception_date > self.config.end_date:
                    reg.debug(f'Extracting data from row {row-1}')

                    # Extract all columns using database column names
                    for db_col in cols:
                        selector = column_to_selector[db_col]

                        if db_col in date_cols:
                            if db_col == 'BirthDate':
                                self.data[db_col].append(self.parse_birth_date(row))
                            else:
                                self.data[db_col].append(self.parse_date(row, selector))
                        else:
                            value = self.extract_cell_data(row, selector)
                            self.data[db_col].append(value if value else 0)

                    samples_found += 1

            except Exception as e:
                reg.debug(f"Error processing row {row}: {e}")

        reg.info(f"Found {samples_found} samples on current page")
        return samples_found
    
    def get_current_page_position(self) -> int:
        """Detect current page position by finding td without <a> tag"""
        for td_index in range(1, 14):
            try:
                self.driver.find_element(
                    By.XPATH, f'{self.config.selectors["GRID_PAGINATION_BASE"]}[{td_index}]/a'
                )
            except Exception:
                # This td has no <a> tag, so it's the current page
                return td_index
        return 0

    def has_next_page(self) -> bool:
        """Check if there's a next page available"""
        try:
            current_position = self.get_current_page_position()
            if current_position == 0:
                return False

            next_page_link = self.driver.find_element(
                By.XPATH, f'{self.config.selectors["GRID_PAGINATION_BASE"]}[{current_position + 1}]/a'
            )
            return True
        except Exception:
            return False

    def go_to_next_page(self) -> bool:
        """Navigate to the next page"""
        try:
            current_position = self.get_current_page_position()
            if current_position == 0:
                return False

            next_page_link = self.driver.find_element(
                By.XPATH, f'{self.config.selectors["GRID_PAGINATION_BASE"]}[{current_position + 1}]/a'
            )
            next_page_link.click()
            self.current_page += 1
            sleep(self.config.sleep_time)
            reg.debug(f'Navigated to page {self.current_page}')
            return True
        except Exception as e:
            reg.warning(f'Cannot navigate to next page: {e}')
            return False
    
    def scrape_client_data(self) -> int:
        """Main scraping method for a client"""
        if not self.login():
            raise Exception("Login failed")

        if not self.navigate_to_client():
            raise Exception(f"Could not navigate to client {self.client}")

        self.empty_pages_count = 0
        total_samples = 0

        # Continue until max consecutive empty pages reached
        while self.empty_pages_count < self.config.max_empty_pages:
            samples_on_page = self.scan_page()
            total_samples += samples_on_page

            # Reset counter if we found samples, increment if page was empty
            if samples_on_page > 0:
                self.empty_pages_count = 0
            else:
                self.empty_pages_count += 1
                reg.debug(f'Empty page {self.empty_pages_count}/{self.config.max_empty_pages}')

            if not self.has_next_page():
                reg.info(f'No more pages available for client {self.client}')
                break

            if not self.go_to_next_page():
                break

        if self.empty_pages_count >= self.config.max_empty_pages:
            reg.info(f'Stopped after {self.empty_pages_count} consecutive empty pages')

        reg.info(f'Completed scraping client {self.client}. Total samples: {total_samples}')
        return total_samples


def prepare_sample_data(scraper_data: Dict[str, List]) -> List[Dict]:
    """Convert scraper data format to database format"""
    samples = []
    num_samples = len(scraper_data[cols[0]]) if cols else 0
    
    for i in range(num_samples):
        sample = {}
        for col in cols:
            if col in scraper_data and i < len(scraper_data[col]):
                sample[col] = scraper_data[col][i]
        samples.append(sample)
    
    return samples


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='LIMS ETL - Extract sample data from LIMS and sync to QuimiOSHub')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD) - newer limit')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD) - older limit')
    parser.add_argument('--max-empty-pages', type=int, help='Max consecutive empty pages before stopping')
    parser.add_argument('--clients', type=str, help='Comma-separated client IDs')
    args = parser.parse_args()

    try:
        config = LIMSConfig()

        # Override config with CLI arguments
        if args.start_date:
            config.start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        if args.end_date:
            config.end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        if args.max_empty_pages:
            config.max_empty_pages = args.max_empty_pages
        if args.clients:
            config.test_clients = [int(c.strip()) for c in args.clients.split(',')]

        reg.info(f'Date range: {config.start_date.date()} (newer) > samples > {config.end_date.date()} (older)')
        reg.info(f'Max consecutive empty pages: {config.max_empty_pages}')

        # Initialize QuimiOSHub API client (required)
        if not config.hub_api_url:
            raise ValueError("HUB_API_URL not configured in .env file")

        reg.info(f'Initializing QuimiOSHub API client: {config.hub_api_url}')
        hub_client = QuimiOSHubClient(config.hub_api_url, config.hub_api_key)

        if not hub_client.health_check():
            raise ConnectionError('QuimiOSHub API is not accessible. Please check the API is running.')

        reg.info('QuimiOSHub API connection successful')
        total_synced = 0

        for client_id in config.test_clients:
            reg.info(f'Starting scrape for client {client_id}')

            try:
                with Scraper(client_id, config) as scraper:
                    samples_count = scraper.scrape_client_data()

                    if scraper.data and any(scraper.data.values()):
                        # Convert scraper data to API format
                        sample_records = prepare_sample_data(scraper.data)

                        # Push directly to QuimiOSHub API
                        synced_count = hub_client.sync_samples(sample_records)
                        reg.info(f'Client {client_id}: {synced_count}/{len(sample_records)} samples synced to QuimiOSHub')
                        total_synced += synced_count
                    else:
                        reg.warning(f'No data found for client {client_id}')

            except Exception as e:
                reg.error(f'Error processing client {client_id}: {e}')
                continue

        reg.info(f'ETL pipeline completed. Synced {total_synced} samples.')

    except Exception as e:
        reg.error(f'Critical error in main execution: {e}')
        raise


if __name__ == '__main__':
    main()