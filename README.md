# LIMS Sample Tracker ETL

Clinical laboratory sample tracking system that scrapes data from legacy LIMS web interface (ASP.NET) and stores it in PostgreSQL database.

## Overview

This ETL pipeline connects to the on-premises LIMS server to extract sample status data and centralize it in a PostgreSQL database. The system uses Selenium WebDriver to automate browser interactions with the legacy web interface.

## Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Chrome/Chromium browser
- ChromeDriver
- Access to LIMS server (internal network)

## Database Setup

1. Install PostgreSQL if not already installed
2. Run the database setup script:
   ```bash
   sudo -u postgres psql -f setup_database.sql
   ```

## Environment Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   ```bash
   # LIMS server (internal network address)
   LIMS_BASE_URL=http://172.16.0.117

   # For development/testing with local HTML fixtures
   LIMS_USE_LOCAL_FIXTURES=false

   # Database credentials
   DB_PASSWORD=lims_secure_pass

   # Your LIMS credentials
   LIMS_USERNAME=your_actual_username
   LIMS_PASSWORD=your_actual_password
   ```

## Installation

1. Install dependencies:
   ```bash
   conda install psycopg2 sqlalchemy selenium pytest python-dotenv -c conda-forge
   ```

2. Install package in development mode:
   ```bash
   pip install -e .
   ```

## Usage

Run the ETL pipeline:
```bash
python -m lims_etl.scraper
```

The scraper will:
1. Connect to the LIMS server
2. Authenticate with provided credentials
3. Extract sample data for configured clients
4. Store data in PostgreSQL database

## Development & Testing

For local development without hitting the production server, you can use the included HTML test fixtures:

```bash
# In .env, set:
LIMS_USE_LOCAL_FIXTURES=true
```

Run tests:
```bash
pytest
```

## Database Schema

The system creates a `samples` table with the following structure:
- `id`: Primary key
- `fecha_grd`, `fecha_recep`, `fec_cap_res`, `fec_libera`, `fec_nac`: Date fields
- `folio_grd`, `cliente_grd`, `paciente_grd`, `est_per_grd`: Numeric identifiers
- `label1`, `suc_proc`, `maquilador`, `label3`: Text fields
- `created_at`: Timestamp when record was inserted

Duplicate detection is handled via unique constraint on `(folio_grd, cliente_grd, fecha_recep)`.

## Notes

- The HTML fixtures (login.html, consulta.html) are for local testing only
- Production deployment connects to the actual LIMS server at http://172.16.0.117
- Requires access to internal laboratory network
