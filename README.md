# LIMS Sample Tracker ETL

Clinical laboratory sample tracking system that scrapes data from legacy LIMS web interface and stores it in PostgreSQL database.

## Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Chrome/Chromium browser
- ChromeDriver

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

2. Edit `.env` with your actual credentials:
   ```bash
   # Database is pre-configured if you ran setup_database.sql
   DB_PASSWORD=lims_secure_pass
   
   # Update with your LIMS credentials
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

## Development

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