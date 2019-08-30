from setuptools import find_packages, setup


setup(
    name='lims-sample-tracker-etl',
    version='0.1.0',
    description='LIMS Sample Tracker ETL Pipeline',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    install_requires=[
        'requests==2.22.0',
        'beautifulsoup4==4.8.0',
        'selenium==3.141.0',
        'webdriver-manager==1.8.2',
        'pandas==0.25.1',
        'python-dotenv==0.10.3',
        'psycopg2-binary==2.8.3',
        'SQLAlchemy==1.3.8',
    ],
    python_requires='>=3.7,<3.8',
    entry_points={'console_scripts': ['lims-scraper=lims_etl.scraper:main']},
)
