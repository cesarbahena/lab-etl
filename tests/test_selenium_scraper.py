"""
Unit tests for deprecated Selenium scraper.

DEPRECATED: This scraper has been replaced by http_scraper.py.
This file is kept for historical reference and comparison.

See benchmark_scraper.py for performance comparison results.
"""

import pytest
from unittest.mock import MagicMock, patch
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException
)
from selenium import webdriver

from lims_etl.selenium_scraper import Scraper
from lims_etl.config import LIMSConfig


@pytest.fixture
def config():
    cfg = LIMSConfig()
    cfg.sleep_time = 0.1
    return cfg


@pytest.fixture
def mock_driver():
    return MagicMock(spec=webdriver.Chrome)


def make_scraper(config, mock_driver):
    scraper = Scraper(client_id=101, config=config)
    scraper.driver = mock_driver
    scraper.current_page = 1
    scraper.empty_pages_count = 0
    return scraper


class TestPagination:
    """Pagination navigation behavior."""

    def test_has_next_page_true_when_link_exists(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)

        def find_element(by, selector):
            if '[2]/a' in selector:
                return MagicMock()
            if '[1]/a' in selector:
                raise NoSuchElementException()
            return MagicMock()

        mock_driver.find_element.side_effect = find_element
        assert scraper.has_next_page() is True

    def test_has_next_page_false_on_last_page(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.side_effect = NoSuchElementException("No next page")
        assert scraper.has_next_page() is False

    def test_go_to_next_page_increments_counter_on_success(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        scraper.current_page = 1

        def find_element(by, selector):
            if '[2]/a' in selector:
                return MagicMock()
            if '[1]/a' in selector:
                raise NoSuchElementException()
            return MagicMock()

        mock_driver.find_element.side_effect = find_element

        with patch('lims_etl.selenium_scraper.sleep'):
            result = scraper.go_to_next_page()

        assert result is True
        assert scraper.current_page == 2

    def test_go_to_next_page_preserves_counter_on_failure(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        scraper.current_page = 1
        mock_driver.find_element.side_effect = NoSuchElementException()

        result = scraper.go_to_next_page()

        assert result is False
        assert scraper.current_page == 1

    def test_go_to_next_page_calls_sleep_on_success(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)

        def find_element(by, selector):
            if '[2]/a' in selector:
                return MagicMock()
            if '[1]/a' in selector:
                raise NoSuchElementException()
            return MagicMock()

        mock_driver.find_element.side_effect = find_element

        with patch('lims_etl.selenium_scraper.sleep') as mock_sleep:
            scraper.go_to_next_page()

        mock_sleep.assert_called_once_with(config.sleep_time)

    def test_go_to_next_page_no_sleep_on_failure(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.side_effect = NoSuchElementException()

        with patch('lims_etl.selenium_scraper.sleep') as mock_sleep:
            scraper.go_to_next_page()

        mock_sleep.assert_not_called()

    def test_sequential_navigation(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        page_num = [1]
        link = MagicMock()

        def find_element(by, selector):
            current = page_num[0]
            if f'[{current + 1}]/a' in selector:
                page_num[0] += 1
                return link
            if f'[{current}]/a' in selector:
                raise NoSuchElementException()
            return MagicMock()

        mock_driver.find_element.side_effect = find_element

        with patch('lims_etl.selenium_scraper.sleep'):
            assert scraper.go_to_next_page() is True
            assert scraper.go_to_next_page() is True

        assert scraper.current_page == 3

    def test_stops_at_last_page(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.side_effect = NoSuchElementException()

        assert scraper.has_next_page() is False

        with patch('lims_etl.selenium_scraper.sleep'):
            assert scraper.go_to_next_page() is False


class TestErrorHandling:
    """Error resilience during pagination."""

    def test_stale_element_on_has_next_page(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.side_effect = StaleElementReferenceException()
        assert scraper.has_next_page() is False

    def test_stale_element_on_click(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        link = MagicMock()
        link.click.side_effect = StaleElementReferenceException()

        def find_element(by, selector):
            if '[2]/a' in selector:
                return link
            if '[1]/a' in selector:
                raise NoSuchElementException()
            return MagicMock()

        mock_driver.find_element.side_effect = find_element
        assert scraper.go_to_next_page() is False
        assert scraper.current_page == 1

    def test_click_intercepted(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        link = MagicMock()
        link.click.side_effect = ElementClickInterceptedException()

        def find_element(by, selector):
            if '[2]/a' in selector:
                return link
            if '[1]/a' in selector:
                raise NoSuchElementException()
            return MagicMock()

        mock_driver.find_element.side_effect = find_element
        assert scraper.go_to_next_page() is False
        assert scraper.current_page == 1


class TestDateParsing:
    """Date parsing from grid cells."""

    def test_valid_date_format(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.return_value.text = "20/03/2023 01:18:00 PM"

        result = scraper.parse_date(2, '_lblFechaRecep')

        assert result.year == 2023
        assert result.month == 3
        assert result.day == 20

    def test_empty_text_returns_nat(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.return_value.text = ""

        result = scraper.parse_date(2, '_lblFechaRecep')

        import pandas as pd
        assert pd.isna(result)

    def test_invalid_format_returns_nat(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.return_value.text = "Not a date"

        result = scraper.parse_date(2, '_lblFechaRecep')

        import pandas as pd
        assert pd.isna(result)

    def test_birth_date_short_format(self, config, mock_driver):
        scraper = make_scraper(config, mock_driver)
        mock_driver.find_element.return_value.text = "21/11/1979"

        result = scraper.parse_birth_date(2)

        assert result.year == 1979
        assert result.month == 11
        assert result.day == 21