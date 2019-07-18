import pytest
from unittest.mock import MagicMock, patch, call
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException
)
from selenium import webdriver

from lims_etl.scraper import Scraper, LIMSConfig
from lims_etl.database import DatabaseManager

@pytest.fixture
def scraper() -> Scraper:
    """Fixture to create a Scraper instance with a mock driver and config."""
    with patch.object(DatabaseManager, '__init__', return_value=None), \
         patch.object(DatabaseManager, 'create_tables', return_value=None):
        config = LIMSConfig()
        config.sleep_time = 0 
        config.selectors = {
            "GRID_PAGINATION_BASE": "//*[@id='pagination-base']"
        }
        
        s = Scraper(client_id=101, config=config)
        s.driver = MagicMock(spec=webdriver.Chrome)
        s.current_page = 1
        return s

def test_has_next_page_success(scraper: Scraper):
    """Test that has_next_page returns True when the next page element exists."""
    mock_element = MagicMock()
    scraper.driver.find_element.return_value = mock_element
    scraper.current_page = 1
    
    assert scraper.has_next_page() is True
    expected_xpath = f'{scraper.config.selectors["GRID_PAGINATION_BASE"]}[{scraper.current_page + 1}]/a'
    scraper.driver.find_element.assert_called_once_with(By.XPATH, expected_xpath)

def test_has_next_page_failure(scraper: Scraper):
    """Test that has_next_page returns False when the element is not found."""
    scraper.current_page = 2
    scraper.driver.find_element.side_effect = NoSuchElementException("Element not found")
    assert scraper.has_next_page() is False
    expected_xpath = f'{scraper.config.selectors["GRID_PAGINATION_BASE"]}[{scraper.current_page + 1}]/a'
    scraper.driver.find_element.assert_called_once_with(By.XPATH, expected_xpath)

@patch('lims_etl.scraper.sleep')
def test_go_to_next_page_success(mock_sleep: MagicMock, scraper: Scraper):
    """Test that go_to_next_page succeeds, increments page, and calls sleep."""
    scraper.current_page = 1
    mock_element = MagicMock()
    scraper.driver.find_element.return_value = mock_element
    
    assert scraper.go_to_next_page() is True
    assert scraper.current_page == 2
    mock_sleep.assert_called_once_with(scraper.config.sleep_time)
    mock_element.click.assert_called_once()

    # Verify find_element was called correctly (only once)
    expected_xpath = f'{scraper.config.selectors["GRID_PAGINATION_BASE"]}[2]/a'
    scraper.driver.find_element.assert_called_once_with(By.XPATH, expected_xpath)

@patch('lims_etl.scraper.sleep')
def test_go_to_next_page_failure_no_link(mock_sleep: MagicMock, scraper: Scraper):
    """Test go_to_next_page fails gracefully if no next-page link exists."""
    scraper.current_page = 1
    scraper.driver.find_element.side_effect = NoSuchElementException("Element not found")
    
    assert scraper.go_to_next_page() is False
    assert scraper.current_page == 1
    
    # Critical: verify no click attempt and no sleep when element not found
    scraper.driver.find_element.assert_called_once()
    mock_sleep.assert_not_called()

@patch('lims_etl.scraper.sleep')
def test_go_to_next_page_click_fails(mock_sleep: MagicMock, scraper: Scraper):
    """Test go_to_next_page fails gracefully if the click action fails."""
    scraper.current_page = 1
    mock_element = MagicMock()
    mock_element.click.side_effect = Exception("Element is not clickable")
    scraper.driver.find_element.return_value = mock_element
    
    assert scraper.go_to_next_page() is False
    # The page should not increment if the click fails and an exception is caught.
    assert scraper.current_page == 1
    mock_element.click.assert_called_once()
    mock_sleep.assert_not_called()

@patch('lims_etl.scraper.sleep')
def test_navigate_multiple_pages(mock_sleep: MagicMock, scraper: Scraper):
    """Test that the scraper can navigate multiple pages sequentially."""
    scraper.current_page = 1
    page2_element = MagicMock()
    page3_element = MagicMock()
    
    def mock_find_element(by, xpath):
        if xpath.endswith('[2]/a'):
            return page2_element
        elif xpath.endswith('[3]/a'):
            return page3_element
        else:
            raise NoSuchElementException()
    
    scraper.driver.find_element.side_effect = mock_find_element

    # Navigate page 1 -> 2
    assert scraper.go_to_next_page() is True
    assert scraper.current_page == 2
    
    # Navigate page 2 -> 3
    assert scraper.go_to_next_page() is True
    assert scraper.current_page == 3

    # Verify each element clicked once
    page2_element.click.assert_called_once()
    page3_element.click.assert_called_once()
    assert mock_sleep.call_count == 2
    
    # Check call count for find_element (1 call per navigation)
    assert scraper.driver.find_element.call_count == 2
    
    # Check that it was called with the correct XPaths in sequence
    expected_xpath_page2 = f'{scraper.config.selectors["GRID_PAGINATION_BASE"]}[2]/a'
    expected_xpath_page3 = f'{scraper.config.selectors["GRID_PAGINATION_BASE"]}[3]/a'
    scraper.driver.find_element.assert_has_calls([
        call(By.XPATH, expected_xpath_page2),
        call(By.XPATH, expected_xpath_page3)
    ], any_order=False)


def test_pagination_reaches_last_page(scraper: Scraper):
    """Test pagination stops correctly at the last page."""
    def mock_find_element(by, xpath):
        if xpath.endswith('[2]/a') or xpath.endswith('[3]/a'):
            return MagicMock()
        else:
            raise NoSuchElementException("No more pages")
    
    scraper.driver.find_element.side_effect = mock_find_element
    scraper.current_page = 1
    
    # Navigate to page 2
    assert scraper.go_to_next_page() is True
    assert scraper.current_page == 2
    
    # Navigate to page 3 
    assert scraper.go_to_next_page() is True
    assert scraper.current_page == 3
    
    # Attempt page 4 should fail
    assert scraper.go_to_next_page() is False
    assert scraper.current_page == 3  # Should stay on page 3
    
    # has_next_page should return False
    assert scraper.has_next_page() is False


def test_stale_element_exception_handling(scraper: Scraper):
    """Test handling of stale element exceptions."""
    # Test has_next_page with stale element
    scraper.driver.find_element.side_effect = StaleElementReferenceException()
    assert scraper.has_next_page() is False
    
    # Test go_to_next_page with stale element during click
    mock_element = MagicMock()
    mock_element.click.side_effect = StaleElementReferenceException()
    scraper.driver.find_element.side_effect = None
    scraper.driver.find_element.return_value = mock_element
    scraper.current_page = 1
    
    assert scraper.go_to_next_page() is False
    assert scraper.current_page == 1


@patch('lims_etl.scraper.sleep')
def test_element_click_intercepted(mock_sleep: MagicMock, scraper: Scraper):
    """Test handling of click interception."""
    mock_element = MagicMock()
    mock_element.click.side_effect = ElementClickInterceptedException()
    scraper.driver.find_element.return_value = mock_element
    scraper.current_page = 1
    
    assert scraper.go_to_next_page() is False
    assert scraper.current_page == 1
    mock_element.click.assert_called_once()
    mock_sleep.assert_not_called()


def test_double_find_element_call_detection(scraper: Scraper):
    """Test that scraper only calls find_element once per operation."""
    mock_element = MagicMock()
    scraper.driver.find_element.return_value = mock_element
    
    # Test has_next_page calls find_element exactly once
    scraper.has_next_page()
    assert scraper.driver.find_element.call_count == 1
    
    # Reset and test go_to_next_page
    scraper.driver.reset_mock()
    scraper.go_to_next_page()
    assert scraper.driver.find_element.call_count == 1
