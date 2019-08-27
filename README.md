# Lab ETL

Clinical laboratory exam tracking system that extracts data from legacy LIMS web interface (ASP.NET WebForms) and syncs to LIMS Hub API.

## Architecture

```
LIMS WebForms (ASP.NET) → HTTP scraper → LIMS Hub API → PostgreSQL
                                      ↑
                                 Airflow DAGs
```

### Components

| Component | Description |
|-----------|-------------|
| `scraper.py` | HTTP-based WebForms scraper |
| `selenium_scraper.py` | Original Selenium scraper (deprecated) |
| `api_client.py` | Client for LIMS Hub REST API |
| `config.py` | Configuration management |
| `lims_etl_dag.py` | Daily ETL Airflow DAG |
| `lims_etl_backfill_dag.py` | Historical backfill DAG |

### Why HTTP over Selenium?

The LIMS uses ASP.NET WebForms with state management (`__VIEWSTATE`, `__EVENTVALIDATION`). Direct HTTP requests handle this pattern efficiently without browser overhead:

- **10x faster** than Selenium in benchmarks
- **5x less memory** usage
- **No browser driver** dependencies
- **Easier deployment** in containerized environments

See `benchmark_scraper.py` for performance comparison.

## Local synthetic smoke test

Start PostgreSQL and the Hub as described in the sibling `../hub/README.md`. Run the WebForms mock in another terminal:

```bash
dotnet run --project webforms_mock/QuimiOSWebForms.csproj --urls http://localhost:5150
```

Install the Python package and pytest, then run the suite. The WebForms E2E tests use port 5150 and detect the already running mock on Windows.

```bash
python -m pip install -e . pytest
python -m pytest tests/ -q
```

To exercise one complete synthetic exam sync, open `python` in the ETL directory and run:

```python
from lims_etl.scraper import HTTPScraper
from lims_etl.api_client import LIMSApiClient

scraper = HTTPScraper("http://localhost:5150")
assert scraper.login()
client = LIMSApiClient("http://localhost:5181")
exams = client.exams_for_partition(scraper.get_samples_page(1), "2023-03-20")
result = client.sync_exams_idempotent(exams, "2023-03-20")
print(result)
```

The mock's first page contains one exam received on 20 March 2023. Repeating the snippet atomically replaces that date's Hub records; `deleted` should then be nonzero. This flow changes only the local demo database configured for Hub. See `../hub/README.md` for the GET request that inspects the partition.

## Standalone scraper

```bash
# Set LIMS_BASE_URL=http://localhost:5150 in your shell, then run the scraper
python -m lims_etl.scraper

# Run benchmark
python benchmark_scraper.py --url http://localhost:5150 --pages 10
```

## Development

```bash
# Start mock WebForms server (requires .NET 10)
dotnet run --project webforms_mock/QuimiOSWebForms.csproj --urls http://localhost:5150

# Run unit tests only
pytest tests/test_scraper.py -v

# Run E2E tests (requires mock server on port 5150)
python -m pytest tests/test_scraper_e2e.py -v
```

## Project Structure

```
lab-etl/
├── src/lims_etl/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py          # Configuration
│   ├── api_client.py      # LIMS Hub API client
│   ├── scraper.py         # Production scraper
│   └── selenium_scraper.py # Legacy Selenium scraper (deprecated)
├── tests/                  # Unit and e2e tests
├── dags/                   # Airflow DAGs
├── webforms_mock/          # Mock WebForms server for testing
└── benchmark_scraper.py    # Performance benchmarks
```

## Configuration

The Airflow DAGs read these Airflow Variables or process environment values. The first three are required for a LIMS connection; `HUB_API_KEY` is optional for the current local Hub.

```
LIMS_BASE_URL=http://localhost:5150
LIMS_USERNAME=your_username
LIMS_PASSWORD=your_password
HUB_API_URL=http://localhost:5181
HUB_API_KEY=
```

The DAGs select exams by `ReceivedAt` and send the batch to `POST /api/exams/partition?partitionDate=yyyy-MM-dd`. Hub validates the entire batch and replaces that partition in one database transaction. An explicit empty batch clears a partition; the DAGs reject an empty selection because their 10-page scrape limit cannot prove the LIMS date is truly empty. The daily DAG verifies the written partition through paged `GET /api/exams` results. Airflow execution and real LIMS behavior have not been verified by the local smoke path; the source timezone and complete historical pagination still need verification.

## License

MIT
