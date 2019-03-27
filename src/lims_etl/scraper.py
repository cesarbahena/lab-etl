#!/usr/bin/env python3
"""
LIMS Sample Tracker ETL Pipeline
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from time import sleep
from datetime import datetime, timedelta
import pandas as pd
import shutil
import logging
import pathlib
import os
import json
from dotenv import load_dotenv
from typing import Dict, List, Optional

load_dotenv() # Load environment variables from .env file

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

# Data types for pandas DataFrame
dtypes = {
    '_lblFechaGrd': 'datetime64[ns]', 
    '_lblFechaRecep': 'datetime64[ns]', 
    '_lblFolioGrd': 'uint32', 
    '_lblClienteGrd': 'uint16', 
    '_lblPacienteGrd': 'uint16', 
    '_lblEstPerGrd': 'uint16', 
    '_Label1': 'category', 
    '_lblFecCapRes': 'datetime64[ns]', 
    '_lblFecLibera': 'datetime64[ns]', 
    '_lblSucProc': 'category', 
    '_lblMaquilador': 'category', 
    '_Label3': 'category', 
    '_lblFecNac': 'datetime64[ns]', 
}

cols = list(dtypes.keys())
date_cols = ['_lblFechaGrd', '_lblFechaRecep', '_lblFecCapRes', '_lblFecLibera', '_lblFecNac']
non_date_dtypes = {k: v for k, v in dtypes.items() if k not in date_cols}
parse_cols = [0, 1, 7, 8, 12]


class LIMSConfig:
    """Configuration class for LIMS credentials and settings"""
    
    def __init__(self):
        # Get credentials from environment variables
        self.username = os.getenv('LIMS_USERNAME', 'demo_user')
        self.password = os.getenv('LIMS_PASSWORD', 'demo_pass')
        
        # Chrome options for WSL/headless operation
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Scraping parameters
        self.start_date = datetime.now() - timedelta(days=1)
        end_date_str = os.getenv('LIMS_END_DATE', '2021-01-15')
        self.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        self.max_fails = 30
        self.sleep_time = 2
        self.output_file = 'Muestras.csv'
        self.test_clients = [101, 102]

        # Load UI selectors from JSON file
        try:
            with open('selectors.json', 'r') as f:
                self.selectors = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("selectors.json not found. Please create it with UI selectors.")
        except json.JSONDecodeError:
            raise json.JSONDecodeError("Error decoding selectors.json. Check file format for valid JSON.", doc="", pos=0)


class Scraper:
    """LIMS web scraper"""
    
    def __init__(self, client_id: int, config: LIMSConfig):
        if not isinstance(client_id, int) or client_id <= 0:
            raise ValueError("client_id must be a positive integer")
        self.client = client_id
        self.config = config
        self.driver: Optional[webdriver.Chrome] = None
        self.data: Dict[str, List] = {col: [] for col in cols}
        self.fails = 0
        self.current_page = 1
        
    def __enter__(self):
        """Context manager entry"""
        self.start_driver()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures driver cleanup"""
        if self.driver:
            self.driver.quit()
            reg.info("Browser closed")
    
    def start_driver(self):
        """Initialize Chrome WebDriver"""
        try:
            service = Service('./chromedriver')
            self.driver = webdriver.Chrome(service=service, options=self.config.chrome_options)
            reg.info("Chrome driver initialized successfully")
        except Exception as e:
            reg.error(f"Failed to start Chrome driver: {e}")
            raise
    
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
                login_path = f'file://{pathlib.Path("login.html").resolve()}'
                self.driver.get(login_path)
                
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
    
    def scan_page(self):
        """Scan current page for sample data within date range"""
        samples_found = 0
        
        # Scan rows 2-11
        for row in range(2, 12):
            try:
                reception_date = self.parse_date(row, '_lblFechaRecep')
                
                # Check if within date range
                if self.config.start_date > reception_date > self.config.end_date:
                    reg.debug(f'Extracting data from row {row-1}')
                    
                    # Extract all columns
                    for col in cols:
                        if col in date_cols:
                            if col == '_lblFecNac':
                                self.data[col].append(self.parse_birth_date(row))
                            else:
                                self.data[col].append(self.parse_date(row, col))
                        else:
                            value = self.extract_cell_data(row, col)
                            self.data[col].append(value if value else 0)
                    
                    samples_found += 1
                else:
                    self.fails += 1
                    
            except Exception as e:
                reg.debug(f"Error processing row {row}: {e}")
                self.fails += 1
        
        reg.info(f"Found {samples_found} samples on current page")
        return samples_found
    
    def has_next_page(self) -> bool:
        """Check if there's a next page available"""
        try:
            next_page_link = self.driver.find_element(
                By.XPATH, f'{self.config.selectors["GRID_PAGINATION_BASE"]}[{self.current_page + 1}]/a'
            )
            return True
        except Exception:
            return False
    
    def go_to_next_page(self) -> bool:
        """Navigate to the next page"""
        try:
            next_page_link = self.driver.find_element(
                By.XPATH, f'{self.config.selectors["GRID_PAGINATION_BASE"]}[{self.current_page + 1}]/a'
            )
            next_page_link.click()
            self.current_page += 1
            sleep(self.config.sleep_time)
            reg.debug(f'Navigated to page {self.current_page}')
            return True
        except Exception as e:
            reg.warning(f'Cannot navigate to page {self.current_page + 1}: {e}')
            return False
    
    def scrape_client_data(self):
        """Main scraping method for a client"""
        if not self.login():
            raise Exception("Login failed")
        
        if not self.navigate_to_client():
            raise Exception(f"Could not navigate to client {self.client}")
        
        self.fails = 0
        total_samples = 0
        
        # Continue until max fails reached
        while self.fails < self.config.max_fails:
            samples_on_page = self.scan_page()
            total_samples += samples_on_page
            
            if not self.has_next_page():
                reg.warning(f'No more pages available for client {self.client}')
                break
            
            if not self.go_to_next_page():
                break
        
        reg.info(f'Completed scraping client {self.client}. Total samples: {total_samples}')
        return total_samples


def create_backup(filename: str):
    """Create backup of existing file"""
    if os.path.exists(filename):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'Respaldo_{timestamp}.csv'
        shutil.copyfile(filename, backup_name)
        reg.info(f'Backup created: {backup_name}')


def load_existing_data(filename: str) -> pd.DataFrame:
    """Load existing CSV data if available"""
    if os.path.exists(filename):
        reg.info(f'Loading existing data from {filename}')
        return pd.read_csv(filename, dtype=non_date_dtypes, parse_dates=parse_cols, dayfirst=True)
    else:
        reg.info('No existing data file found, starting fresh')
        return pd.DataFrame({col: [] for col in cols})


def save_data(df: pd.DataFrame, filename: str):
    """Save DataFrame to CSV"""
    reg.info(f'Saving data to {filename}')
    df.to_csv(filename, index=False)


def main():
    """Main execution function"""
    try:
        config = LIMSConfig()
        
        # Load existing data
        create_backup(config.output_file)
        master_df = load_existing_data(config.output_file)
        
        # For testing, use a single client. In production, this could be configurable
        test_clients = config.test_clients
        
        for client_id in test_clients:
            reg.info(f'Starting scrape for client {client_id}')
            
            try:
                with Scraper(client_id, config) as scraper:
                    samples_count = scraper.scrape_client_data()
                    
                    # Convert scraped data to DataFrame
                    client_df = pd.DataFrame(scraper.data)
                    if not client_df.empty:
                        # Apply data types
                        client_df = client_df.astype(dtype=dtypes, errors='ignore')
                        
                        # Append to master DataFrame
                        master_df = pd.concat([master_df, client_df], ignore_index=True)
                        
                        # Save after each client (incremental backup)
                        save_data(master_df, config.output_file)
                        reg.info(f'Client {client_id} completed: {samples_count} samples processed')
                    else:
                        reg.warning(f'No data found for client {client_id}')
                        
            except Exception as e:
                reg.error(f'Error processing client {client_id}: {e}')
                continue
        
        reg.info(f'ETL pipeline completed. Final dataset: {len(master_df)} total samples')
        
    except Exception as e:
        reg.error(f'Critical error in main execution: {e}')
        raise


if __name__ == '__main__':
    main()