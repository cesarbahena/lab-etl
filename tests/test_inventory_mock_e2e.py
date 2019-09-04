"""Inventory save behavior against the local WebForms stand-in."""

from decimal import Decimal
import re

from bs4 import BeautifulSoup
import pytest

from lims_etl.scraper import HTTPScraper
from test_scraper_e2e import mock_server  # noqa: F401 - shared server fixture


INVENTORY_PATH = "/Inventarios/ConsumoReacLabMasivo.aspx"
ROW_PREFIX = "ctl00$ContentMasterPage$grdConsumo$ctl"


def inventory_session(base_url):
    scraper = HTTPScraper(base_url, "demo_user", "demo_pass")
    assert scraper.login()
    return scraper.session


def read_form(session, base_url):
    response = session.get(base_url + INVENTORY_PATH)
    response.raise_for_status()
    assert "grdConsumo" in response.text
    soup = BeautifulSoup(response.text, "html.parser")
    fields = {
        element["name"]: element.get("value", "")
        for element in soup.select("form input[name]")
        if element.get("type") != "checkbox" or element.has_attr("checked")
    }
    for element in soup.select("form select[name]"):
        selected = element.select_one("option[selected]") or element.select_one("option")
        fields[element["name"]] = selected.get("value", "") if selected else ""
    return soup, fields


def stock_and_row(soup, code):
    reagent = next(
        item for item in soup.select("span[id$='_lblRVO']")
        if item.get_text(strip=True) == code
    )
    row = re.search(r"_ctl(\d+)_lblRVO$", reagent["id"]).group(1)
    stock = soup.select_one("#ctl00_ContentMasterPage_grdConsumo_ctl{}_lblExistFinal".format(row))
    return Decimal(stock.get_text(strip=True)), row


def save(session, base_url, fields):
    fields["ctl00$ContentMasterPage$btnGuardaMasivo"] = "Guardar"
    response = session.post(base_url + INVENTORY_PATH, data=fields)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def field(row, name):
    return "{}{}${}".format(ROW_PREFIX, row, name)


@pytest.mark.parametrize("page", ["/Login", "/Consulta", INVENTORY_PATH])
def test_pages_render_complete_webforms_state(mock_server, page):
    session = inventory_session(mock_server)
    response = session.get(mock_server + page)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    generator = soup.select_one("input[name='__VIEWSTATEGENERATOR']")
    assert generator is not None
    assert re.fullmatch(r"[0-9A-F]{8}", generator["value"])
    for name in ("__VIEWSTATE", "__EVENTVALIDATION"):
        state = soup.select_one("input[name='{}']".format(name))
        assert state is not None and state["value"]


def test_consumption_updates_stock_for_other_sessions(mock_server):
    first = inventory_session(mock_server)
    second = inventory_session(mock_server)
    before_page, fields = read_form(first, mock_server)
    before, row = stock_and_row(before_page, "ACVALPMT")
    fields[field(row, "txtPacientes")] = "2"
    result = save(first, mock_server, fields)
    assert result.select_one(".success") is not None
    assert stock_and_row(result, "ACVALPMT")[0] == before - 2
    after_page, _ = read_form(second, mock_server)
    assert stock_and_row(after_page, "ACVALPMT")[0] == before - 2
    assert result.select_one("input[name='{}']".format(field(row, "txtPacientes")))["value"] == "0"


def test_signed_decimal_corrections_change_stock_in_both_directions(mock_server):
    session = inventory_session(mock_server)
    before_page, fields = read_form(session, mock_server)
    before, row = stock_and_row(before_page, "AFP_MTY")
    fields[field(row, "txtPacientes")] = "-1.25"
    increased = save(session, mock_server, fields)
    assert increased.select_one(".success") is not None
    assert stock_and_row(increased, "AFP_MTY")[0] == before + Decimal("1.25")

    current_page, fields = read_form(session, mock_server)
    fields[field(row, "txtPacientes")] = "0.5"
    decreased = save(session, mock_server, fields)
    assert decreased.select_one(".success") is not None
    assert stock_and_row(decreased, "AFP_MTY")[0] == before + Decimal("0.75")


@pytest.mark.parametrize("invalid_field,invalid_value", [
    ("txtControlCapMGrd", "bad"),
    ("txtPacientes", "100000"),
    ("hfIDProducto", "999999"),
])
def test_invalid_batch_does_not_apply_valid_row(mock_server, invalid_field, invalid_value):
    session = inventory_session(mock_server)
    before_page, fields = read_form(session, mock_server)
    valid_before, valid_row = stock_and_row(before_page, "BHCGMTY")
    invalid_before, invalid_row = stock_and_row(before_page, "CA125MTY")
    fields[field(valid_row, "txtPacientes")] = "1"
    fields[field(invalid_row, invalid_field)] = invalid_value
    result = save(session, mock_server, fields)
    assert result.select_one(".error") is not None
    assert stock_and_row(result, "BHCGMTY")[0] == valid_before
    assert stock_and_row(result, "CA125MTY")[0] == invalid_before


def test_stale_form_cannot_overwrite_newer_stock(mock_server):
    first = inventory_session(mock_server)
    second = inventory_session(mock_server)
    first_page, first_fields = read_form(first, mock_server)
    second_page, second_fields = read_form(second, mock_server)
    before, row = stock_and_row(first_page, "CA153MTY")
    assert stock_and_row(second_page, "CA153MTY")[0] == before

    first_fields[field(row, "txtPacientes")] = "1"
    assert save(first, mock_server, first_fields).select_one(".success") is not None
    second_fields[field(row, "txtPacientes")] = "2"
    stale = save(second, mock_server, second_fields)
    assert stale.select_one(".error") is not None
    assert stock_and_row(stale, "CA153MTY")[0] == before - 1

    replay = save(first, mock_server, first_fields)
    assert replay.select_one(".error") is not None
    assert stock_and_row(replay, "CA153MTY")[0] == before - 1
