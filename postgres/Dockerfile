FROM timescale/timescaledb-ha:pg15-latest

# Switch to root to install tools if needed
USER root

# Copy SQL schema for initialization
COPY init.sql /docker-entrypoint-initdb.d/init.sql

# Switch back to postgres user
USER postgres
