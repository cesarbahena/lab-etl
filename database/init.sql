-- LIMS ETL Database Initialization
-- Professional PostgreSQL setup for production environments
-- Usage: sudo -u postgres psql -f database/init.sql

-- Create user only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'lims_user') THEN
        CREATE USER lims_user WITH PASSWORD 'lims_secure_pass';
        RAISE NOTICE 'User lims_user created successfully';
    ELSE
        RAISE NOTICE 'User lims_user already exists';
    END IF;
END
$$;

-- Create database only if it doesn't exist
SELECT 'CREATE DATABASE lims_etl OWNER lims_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'lims_etl')\gexec

-- Connect to the database
\c lims_etl;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO lims_user;

-- Grant privileges on existing tables and sequences
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lims_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO lims_user;

-- Grant default privileges for future tables and sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO lims_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO lims_user;

-- Success message
SELECT 'Database lims_etl initialized successfully for user lims_user' AS result;