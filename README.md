# LIMS Sample Tracker ETL

Web scraper for extracting sample data from legacy LIMS system.

## Setup

1. Install dependencies:
```bash
pip install -e .
```

2. Install ChromeDriver:
```bash
# Download chromedriver and place in project root
```

3. Create configuration files:
```bash
cp .env.example .env  # Add credentials
cp selectors.example.json selectors.json  # Add UI selectors
```

## Usage

Run the scraper:
```bash
lims-scraper
```

Or as module:
```bash
python -m lims_etl.scraper
```

## Testing

```bash
pytest tests/
```

## Files

- `src/lims_etl/scraper.py` - Main scraper logic
- `selectors.json` - UI element selectors for web scraping
- `consulta.html`, `login.html` - Mock HTML for testing
- `Muestras.csv` - Output data file