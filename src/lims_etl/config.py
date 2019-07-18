import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from selenium import webdriver
from .database import DatabaseManager

load_dotenv() # Load environment variables from .env file

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
        self.test_clients = [101, 102]
        
        # Database configuration
        self.db_manager = DatabaseManager()
        self.db_manager.create_tables()

        # Load UI selectors from JSON file
        try:
            with open('selectors.json', 'r') as f:
                self.selectors = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("selectors.json not found. Please create it with UI selectors.")
        except json.JSONDecodeError:
            raise json.JSONDecodeError("Error decoding selectors.json. Check file format for valid JSON.", doc="", pos=0)
