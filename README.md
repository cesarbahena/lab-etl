# LIMS Sample Tracker ETL

Clinical laboratory sample tracking system that scrapes data from legacy LIMS web interface (ASP.NET WebForms) and syncs to QuimiOSHub API.

## Architecture

```
LIMS WebForms (ASP.NET) → Selenium Scraper → QuimiOSHub API → lab-hub DB
                                     ↑
                               Airflow DAGs
```

## Features

- Selenium-based web scraping with local HTML fixture support
- Idempotent sync with partition-based DELETE + INSERT pattern
- Retry logic with exponential backoff
- Airflow orchestration for scheduled and backfill runs

## Quick Start

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run locally with fixtures
python -m lims_etl --clients 101,102
```

## Environment

```bash
cp .env.example .env

# Local development with fixtures
LIMS_USE_LOCAL_FIXTURES=true
HUB_API_URL=http://localhost:8080
```

## Testing

```bash
pytest tests/ -v
```

## Airflow Setup

```bash
docker-compose up -d
# UI: http://localhost:8090 (admin/admin)
```

## Idempotent Sync

The API client supports partition-based idempotent writes:

```python
client.sync_samples_idempotent(samples, partition_date='2024-01-15')
# Deletes existing records for that date, then inserts fresh data
```

This ensures safe re-runs for backfills and retries without duplicates.

## Database Schema

Samples table with columns:
- `folio`, `client_id`, `patient_id`, `exam_id`, `exam_name`
- `created_at`, `received_at`, `processed_at`, `validated_at`
- `location`, `outsourcer`, `priority`, `birth_date`