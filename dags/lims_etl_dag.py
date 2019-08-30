"""Daily exam import from the laboratory LIMS."""

import logging
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


def check_hub(**context):
    from lims_etl.api_client import LIMSApiClient
    if not LIMSApiClient(setting('HUB_API_URL', 'http://app:8080'),
                         setting('HUB_API_KEY')).health_check():
        raise RuntimeError('Hub is unavailable')


def import_day(day, **context):
    return sync_partition(day, setting('LIMS_BASE_URL'),
                          setting('LIMS_USERNAME'), setting('LIMS_PASSWORD'),
                          setting('HUB_API_URL', 'http://app:8080'),
                          setting('HUB_API_KEY'))


def check_day(**context):
    summary = context['ti'].xcom_pull(task_ids='import_day')
    return verify_partition(summary, setting('HUB_API_URL', 'http://app:8080'))


with DAG('lims_etl_daily', description='Import received exams from LIMS',
         schedule_interval='0 6 * * *', start_date=datetime(2019, 8, 1),
         catchup=False, max_active_runs=1,
         default_args={'owner': 'lab', 'retries': 3,
                       'retry_delay': timedelta(minutes=5)}) as dag:
    health = PythonOperator(task_id='check_hub', python_callable=check_hub,
                            provide_context=True)
    import_exams = PythonOperator(task_id='import_day', python_callable=import_day,
                                  op_kwargs={'day': '{{ ds }}'}, provide_context=True)
    verify = PythonOperator(task_id='verify_day', python_callable=check_day,
                            provide_context=True)
    health >> import_exams >> verify
