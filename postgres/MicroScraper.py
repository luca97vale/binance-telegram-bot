# requirements.txt
"""
fastapi==0.104.1
uvicorn==0.24.0
psycopg2-binary==2.9.9
httpx==0.25.2
apscheduler==3.10.4
pydantic==2.5.0
python-dotenv==1.0.0
"""

# .env file
"""
DATABASE_HOST=localhost
DATABASE_NAME=crypto_total
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
DATABASE_PORT=5432
TELEGRAM_BOT_URL=http://localhost:8000
TELEGRAM_CHAT_ID=your_chat_id
LOG_LEVEL=INFO
"""





# docker-compose.yml
"""
version: '3.8'

services:
  crypto-scheduler:
    build: .
    container_name: crypto-portfolio-scheduler
    ports:
      - "8001:8001"
    environment:
      - DATABASE_HOST=postgres
      - DATABASE_NAME=crypto_total
      - DATABASE_USER=crypto_user
      - DATABASE_PASSWORD=crypto_password
      - DATABASE_PORT=5432
      - TELEGRAM_BOT_URL=http://telegram-bot:8000
      - LOG_LEVEL=INFO
    depends_on:
      - postgres
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: crypto-postgres
    environment:
      - POSTGRES_DB=crypto_total
      - POSTGRES_USER=crypto_user
      - POSTGRES_PASSWORD=crypto_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
"""

# Dockerfile
"""
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "main.py"]
"""