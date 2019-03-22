import pytest
from unittest.mock import MagicMock, patch
from lims_etl.scraper import Scraper, LIMSConfig
from selenium.webdriver.common.by import By

# Mock LIMSConfig for testing
@pytest.fixture
def mock_config():
    config = LIMSConfig()
    config.sleep_time = 0 # No actual sleep during tests
    config.selectors = {
        "GRID_PAGINATION_BASE": "//*[@id=\"ctl00_ContentMasterPage_grdConsultaOT\"]/tbody/tr[12]/td/table/tbody/tr/td"
    }
    return config

# Mock WebDriver for testing
@pytest.fixture
def mock_driver():
    driver = MagicMock()
    return driver

def test_has_next_page_true(mock_driver, mock_config):
    """
    Test that has_next_page returns True when a next page link is found.
    """
    scraper = Scraper(client_id=1, config=mock_config)
    scraper.driver = mock_driver
    scraper.current_page = 1

    # Simulate finding the next page link
    mock_driver.find_element.return_value = MagicMock()

    assert scraper.has_next_page() is True
    mock_driver.find_element.assert_called_with(
        By.XPATH, f'{mock_config.selectors["GRID_PAGINATION_BASE"]}[{scraper.current_page + 1}]/a'
    )

def test_has_next_page_false(mock_driver, mock_config):
    scraper = Scraper(client_id=1, config=mock_config)
    scraper.driver = mock_driver
    scraper.current_page = 1

    # Simulate not finding the next page link
    mock_driver.find_element.side_effect = Exception("Element not found")

    assert scraper.has_next_page() is False
    mock_driver.find_element.assert_called_with(
        By.XPATH, f'{mock_config.selectors["GRID_PAGINATION_BASE"]}[{scraper.current_page + 1}]/a'
    )

def test_go_to_next_page_success(mock_driver, mock_config):
    """
    Test that go_to_next_page navigates to the next page successfully.
    """
    scraper = Scraper(client_id=1, config=mock_config)
    scraper.driver = mock_driver
    scraper.current_page = 1

    # Simulate finding the next page link
    mock_next_page_link = MagicMock()
    mock_driver.find_element.return_value = mock_next_page_link

    assert scraper.go_to_next_page() is True
    mock_driver.find_element.assert_called_with(
        By.XPATH, f'{mock_config.selectors["GRID_PAGINATION_BASE"]}[{scraper.current_page}]/a'
    )
    mock_next_page_link.click.assert_called_once()
    assert scraper.current_page == 2

def test_go_to_next_page_failure(mock_driver, mock_config):
    """
    Test that go_to_next_page handles failure to navigate to the next page.
    """
    scraper = Scraper(client_id=1, config=mock_config)
    scraper.driver = mock_driver
    scraper.current_page = 1

    # Simulate not finding the next page link
    mock_driver.find_element.side_effect = Exception("Element not found")

    assert scraper.go_to_next_page() is False
    mock_driver.find_element.assert_called_with(
        By.XPATH, f'{mock_config.selectors["GRID_PAGINATION_BASE"]}[{scraper.current_page + 1}]/a'
    )
    assert scraper.current_page == 1 # Should not increment page on failure
