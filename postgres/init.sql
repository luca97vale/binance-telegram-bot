-- Create database (optional if you want a different name)
CREATE DATABASE crypto_total;

-- No need to create user; Docker uses POSTGRES_USER/POSTGRES_PASSWORD

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE crypto_total TO crypto_user;

-- Connect to the new database
\c crypto_total

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Grant schema permissions
GRANT USAGE ON SCHEMA public TO crypto_user;
GRANT CREATE ON SCHEMA public TO crypto_user;

CREATE TABLE IF NOT EXISTS crypto_total (
    time DATE NOT NULL PRIMARY KEY,
    total_usd NUMERIC(18,8) NOT NULL
);

SELECT create_hypertable('crypto_total', 'time', if_not_exists => TRUE);
