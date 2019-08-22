# LIMS Sample Tracker ETL

Clinical laboratory exam tracking system that extracts data from legacy LIMS web interface (ASP.NET WebForms) and syncs to LIMS Hub API.

## Architecture

```
LIMS WebForms (ASP.NET) → HTTP Scraper → LIMS Hub API → lab-hub DB
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

## Quick Start

```bash
# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run HTTP scraper against mock server
python -m lims_etl.scraper --url http://localhost:5090

# Run tests
pytest tests/

# Run benchmark
python benchmark_scraper.py --url http://localhost:5090 --pages 10
```

## Development

```bash
# Start mock WebForms server (requires .NET 10)
cd webforms_mock && dotnet run --urls="http://localhost:5090"

# Run unit tests only
pytest tests/test_scraper.py -v

# Run e2e tests (requires mock server)
pytest tests/test_scraper_e2e.py -v
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

See `.env.example` for required environment variables:

```
LIMS_URL=https://lims.example.com
LIMS_USER=your_username
LIMS_PASSWORD=your_password
HUB_API_URL=http://lab-hub:8080
HUB_API_KEY=your_api_key
DB_HOST=postgres
DB_PORT=5432
DB_NAME=lims_dev
DB_USER=lims_dev
DB_PASSWORD=dev_password
```

## License

MIT