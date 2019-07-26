import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from selenium import webdriver

load_dotenv() # Load environment variables from .env file

class LIMSConfig:
    """Configuration class for LIMS credentials and settings"""

    def __init__(self):
        # Get credentials from environment variables
        self.username = os.getenv('LIMS_USERNAME', 'demo_user')
        self.password = os.getenv('LIMS_PASSWORD', 'demo_pass')

        # LIMS server configuration
        self.base_url = os.getenv('LIMS_BASE_URL', 'http://172.16.0.117')
        self.use_local_fixtures = os.getenv('LIMS_USE_LOCAL_FIXTURES', 'false').lower() == 'true'

        # QuimiOSHub API configuration (required)
        self.hub_api_url = os.getenv('HUB_API_URL', '')
        self.hub_api_key = os.getenv('HUB_API_KEY', '')

        # Chrome options for WSL/headless operation
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')

        # Scraping parameters - date range filtering
        start_date_str = os.getenv('LIMS_START_DATE')
        if start_date_str:
            self.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            self.start_date = datetime.now() - timedelta(days=1)

        end_date_str = os.getenv('LIMS_END_DATE', '2021-01-15')
        self.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        self.max_fails = int(os.getenv('LIMS_MAX_FAILS', '30'))
        self.sleep_time = int(os.getenv('LIMS_SLEEP_TIME', '2'))
        self.test_clients = [101, 102]

        # Load UI selectors from JSON file
        try:
            with open('selectors.json', 'r') as f:
                self.selectors = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("selectors.json not found. Please create it with UI selectors.")
        except json.JSONDecodeError:
            raise json.JSONDecodeError("Error decoding selectors.json. Check file format for valid JSON.", doc="", pos=0)

    def get_login_url(self) -> str:
        """Get login page URL (production server or local test fixture)"""
        if self.use_local_fixtures:
            import pathlib
            return f'file://{pathlib.Path("login.html").resolve()}'
        return f'{self.base_url}/'

    def get_consulta_url(self) -> str:
        """Get consultation page URL (production server or local test fixture)"""
        if self.use_local_fixtures:
            import pathlib
            return f'file://{pathlib.Path("consulta.html").resolve()}'
        return f'{self.base_url}/FasePreAnalitica/ConsultaOrdenTrabajo.aspx'
