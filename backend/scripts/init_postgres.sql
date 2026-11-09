-- MedRisk local PostgreSQL bootstrap (development only).
-- Run as a superuser:  psql -U postgres -f backend/scripts/init_postgres.sql
-- Change the password before using this database anywhere shared.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medrisk') THEN
        CREATE ROLE medrisk LOGIN PASSWORD 'medrisk';
    END IF;
END
$$;

SELECT 'CREATE DATABASE medrisk OWNER medrisk TEMPLATE template0 '
       'ENCODING ''UTF8'' LC_COLLATE ''C'' LC_CTYPE ''C'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'medrisk')
\gexec
