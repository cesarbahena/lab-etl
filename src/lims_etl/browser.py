import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from src.lims_etl.config import LIMSConfig

reg = logging.getLogger(__name__)

class Browser:
    """Manages the Selenium WebDriver lifecycle."""

    def __init__(self, config: LIMSConfig):
        self.config = config
        self.driver: webdriver.Chrome = None

    def __enter__(self):
        """Context manager entry: Initializes the WebDriver."""
        self.start_driver()
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: Ensures the WebDriver is quit."""
        self.quit_driver()

    def start_driver(self):
        """Initializes the Chrome WebDriver."""
        try:
            service = Service('./chromedriver')
            self.driver = webdriver.Chrome(service=service, options=self.config.chrome_options)
            reg.info("Chrome driver initialized successfully")
        except Exception as e:
            reg.error(f"Failed to start Chrome driver: {e}")
            raise

    def quit_driver(self):
        """Quits the Chrome WebDriver."""
        if self.driver:
            self.driver.quit()
            reg.info("Browser closed")
