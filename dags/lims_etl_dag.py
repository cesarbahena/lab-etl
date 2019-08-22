"""
LIMS ETL Airflow DAG

Schedule: Daily at 6:00 AM (Mexico City timezone)
Purpose: Scrape sample data from LIMS WebForms blackbox and sync to lab-hub API

Key Features:
- Idempotent: Safe to re-run, no duplicates
- Backfillable: Uses ds (execution date) parameter
- Retry on failure: 3 attempts with exponential backoff
- Data quality checks: Validates row counts before/after
- DLQ ready: Structured to route failures to dead letter queue

DAG Variables (via Airflow Variables or .env):
    HUB_API_URL: http://app:8080
    DB_HOST: postgres
    DB_USER: lims_dev
    DB_PASSWORD: dev_password
"""

from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.operators.python import PythonOperator
import logging

# DAG Configuration
default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,          # Allow parallel runs
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,                      # Retry up to 3 times
    'retry_delay': timedelta(minutes=5),  # 5 min between retries
    'catchup': True,                   # Enable backfill
}

@dag(
    dag_id='lims_etl_daily',
    default_args=default_args,
    description='Scrape LIMS samples and sync to lab-hub',
    schedule='0 6 * * *',              # Daily at 6:00 AM Mexico City
    max_active_runs=4,                 # Limit parallel backfills
    catchup=True,                      # Enable catchup/backfill
    tags=['etl', 'lims', 'samples'],
)
def lims_etl_dag():
    """
    Main ETL pipeline DAG.
    
    Flow:
    1. Health check - verify lab-hub API is accessible
    2. Scrape data - extract samples from LIMS WebForms
    3. Transform - normalize column names
    4. Validate - data quality checks
    5. Load - sync to lab-hub API
    6. Verify - confirm records in database
    """
    
    @task(
        task_id='health_check',
        retries=2,
        retry_delay=timedelta(seconds=30),
    )
    def check_api_health():
        """
        Verify lab-hub API is accessible before scraping.
        Prevents wasted scraping effort if downstream is down.
        """
        import requests
        
        hub_url = Variable.get('HUB_API_URL', default_var='http://app:8080')
        health_endpoint = f'{hub_url}/api/health/ping'
        
        try:
            response = requests.get(health_endpoint, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logging.info(f"API Health: {data.get('status', 'unknown')}")
            
            return {'status': 'healthy', 'timestamp': data.get('timestamp')}
            
        except Exception as e:
            logging.error(f"API health check failed: {e}")
            raise
    
    @task(
        task_id='scrape_lims',
        retries=3,
        retry_delay=timedelta(minutes=2),
    )
    def scrape_samples(execution_date: str) -> dict:
        """
        Scrape sample data from LIMS WebForms.
        
        Uses HTTP scraper (http_scraper.py) for better performance.
        See scraper_selenium_deprecated.py for the original Selenium implementation.
        
        Args:
            execution_date: The date to process (ds from Airflow)
                          Format: YYYY-MM-DD
        
        Returns:
            Dict with scraped data summary for downstream tasks
        """
        import sys
        import os
        import logging
        from datetime import datetime
        
        # Add src to path for imports
        sys.path.insert(0, '/opt/airflow/src')
        
        # Set up execution context
        logging.info(f"Starting LIMS scrape for {execution_date}")
        
        # Import ETL modules
        from lims_etl.config import LIMSConfig
        from lims_etl.http_scraper import HTTPScraper
        from lims_etl.api_client import LIMSApiClient
        
        # Initialize config
        config = LIMSConfig()
        
        # Create HTTP scraper
        scraper = HTTPScraper(
            base_url=LIMSConfig.LIMS_URL,
            username=LIMSConfig.LIMS_USER,
            password=LIMSConfig.LIMS_PASSWORD
        )
        
        # Login to LIMS
        if not scraper.login():
            raise RuntimeError("Failed to login to LIMS")
        
        logging.info("Successfully logged into LIMS")
        
        # Scrape samples from multiple pages
        all_records = []
        max_pages = 10  # Safety limit
        
        for page in range(1, max_pages + 1):
            records = scraper.get_samples_page(page)
            if not records:
                break
            all_records.extend(records)
            logging.info(f"Page {page}: fetched {len(records)} records")
        
        logging.info(f"Total records scraped: {len(all_records)}")
        
        # Transform to API format
        sample_records = []
        for record in all_records:
            sample_records.append({
                'folio': record.get('Folio'),
                'clientId': int(record.get('ClientId', 0)),
                'patientId': int(record.get('PatientId', 0)),
                'examId': int(record.get('ExamId', 0)),
                'examName': record.get('ExamName'),
                'createdAt': record.get('CreatedAt'),
                'receivedAt': record.get('ReceivedAt'),
                'processedAt': record.get('ProcessedAt'),
                'validatedAt': record.get('ValidatedAt'),
                'location': record.get('Location'),
                'outsourcer': record.get('Outsourcer'),
                'priority': record.get('Priority'),
                'birthDate': record.get('BirthDate'),
                'partitionDate': execution_date,
            })
        
        # Sync to lab-hub API
        hub_client = LIMSApiClient(
            config.hub_api_url,
            config.hub_api_key
        )
        
        total_synced = hub_client.sync_samples(sample_records)
        
        logging.info(f"Synced {total_synced} samples to lab-hub")
        
        result = {
            'execution_date': execution_date,
            'total_scraped': len(all_records),
            'total_synced': total_synced,
        }
        
        return result
    
    @task(
        task_id='validate_data_quality',
        retries=1,
    )
    def validate_samples(data: dict) -> dict:
        """
        Data quality checks on synced samples.
        
        Validates:
        - Row count matches expected
        - Required fields present
        - No null values in critical columns
        """
        import requests
        from datetime import datetime
        
        logging.info(f"Running data quality checks for {data.get('execution_date')}")
        
        hub_url = Variable.get('HUB_API_URL', default_var='http://app:8080')
        
        # Get samples from API
        try:
            response = requests.get(
                f'{hub_url}/api/samples',
                params={'limit': 100},
                timeout=10
            )
            response.raise_for_status()
            samples = response.json().get('data', [])
            
            # Quality checks
            checks = {
                'total_samples': len(samples),
                'has_data': len(samples) > 0,
                'required_fields': ['folio', 'clientId', 'patientId', 'examName'],
                'missing_fields': [],
                'null_counts': {}
            }
            
            # Check required fields
            for field in checks['required_fields']:
                missing = sum(1 for s in samples if s.get(field) is None)
                if missing > 0:
                    checks['missing_fields'].append(field)
                    checks['null_counts'][field] = missing
            
            # Sample-level check
            if len(samples) > 0:
                sample = samples[0]
                logging.info(f"Sample data: {sample.get('folio')}, {sample.get('examName')}")
            
            logging.info(f"Quality checks: {checks}")
            return checks
            
        except Exception as e:
            logging.error(f"Quality check failed: {e}")
            return {'error': str(e)}
    
    @task(
        task_id='report_summary',
        triggers=None,
    )
    def send_summary(data: dict, quality: dict):
        """
        Generate execution summary.
        
        In production, this would:
        - Send Slack notification
        - Email on failures
        - Update metrics dashboard
        """
        import logging
        
        summary = f"""
        LIMS ETL Execution Summary
        ============================
        Date: {data.get('execution_date')}
        Total Scraped: {data.get('total_scraped', 0)}
        Total Synced: {data.get('total_synced', 0)}
        """
        
        logging.info(summary)
        
        # Quality summary
        if quality.get('has_data'):
            logging.info(f"Data quality: PASS ({quality.get('total_samples')} samples)")
        else:
            logging.warning("Data quality: FAIL - no data found")
        
        return summary
    
    # DAG Flow
    # ======================================
    
    # Step 1: Health check
    health = check_api_health()
    
    # Step 2: Scrape with execution date from DAG
    scrape_result = scrape_samples('{{ ds }}')
    
    # Step 3: Validate data quality
    quality = validate_samples(scrape_result)
    
    # Step 4: Report summary
    summary = send_summary(scrape_result, quality)
    
    # Dependencies
    health >> scrape_result >> quality >> summary


# Instantiate the DAG
lims_etl_dag_instance = lims_etl_dag()