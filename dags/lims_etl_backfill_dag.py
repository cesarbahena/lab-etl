"""Manually triggered received-date backfill.

Pass start_date and end_date (inclusive) in the DagRun configuration.
Each date is verified before the next is replaced, so a failed run can
be restarted safely after the source or Hub is repaired.
"""

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python_operator import PythonOperator

sys.path.insert(0, '/opt/airflow/src')
from lims_etl.jobs import sync_partition, verify_partition


def setting(name, default=''):
    return Variable.get(name, default_var=os.getenv(name, default))


def import_range(**context):
    config = context['dag_run'].conf or {}
    start = datetime.strptime(config['start_date'], '%Y-%m-%d').date()
    end = datetime.strptime(config['end_date'], '%Y-%m-%d').date()
    if end < start or (end - start).days > 366:
        raise ValueError('Backfill range must contain 1 to 367 dates')
    day = start
    results = []
    while day <= end:
        date_text = day.isoformat()
        summary = sync_partition(date_text, setting('LIMS_BASE_URL'),
                                 setting('LIMS_USERNAME'), setting('LIMS_PASSWORD'),
                                 setting('HUB_API_URL', 'http://app:8080'),
                                 setting('HUB_API_KEY'))
        results.append(verify_partition(summary,
                                        setting('HUB_API_URL', 'http://app:8080')))
        day += timedelta(days=1)
    return results


with DAG('lims_etl_backfill', description='Import a range of received dates',
         schedule_interval=None, start_date=datetime(2019, 8, 1),
         catchup=False, max_active_runs=1,
         default_args={'owner': 'lab', 'retries': 1,
                       'retry_delay': timedelta(minutes=5)}) as dag:
    PythonOperator(task_id='import_range', python_callable=import_range,
                   provide_context=True)
