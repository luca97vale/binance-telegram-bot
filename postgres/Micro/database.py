# database.py
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
import logging
from config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.connection_params = {
            'host': settings.database_host,
            'database': settings.database_name,
            'user': settings.database_user,
            'password': settings.database_password,
            'port': settings.database_port
        }

    def get_connection(self):
        """Get database connection"""
        try:
            conn = psycopg2.connect(**self.connection_params)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise

    def init_hypertable(self):
        """Initialize the hypertable (run once)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create the table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crypto_total (
                    time DATE NOT NULL PRIMARY KEY,
                    total_usd NUMERIC(18,8) NOT NULL
                );
            """)

            # Convert to hypertable
            cursor.execute("""
                SELECT create_hypertable('crypto_total', 'time', 
                                       chunk_time_interval => INTERVAL '1 month',
                                       if_not_exists => TRUE);
            """)

            # Create index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_crypto_total_time 
                ON crypto_total (time DESC);
            """)

            conn.commit()
            logger.info("✅ Hypertable initialized successfully")

        except Exception as e:
            logger.error(f"❌ Error initializing hypertable: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def save_total_value(self, date, total_value: Decimal):
        """Save total portfolio value to database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO crypto_total (time, total_usd) 
                VALUES (%s, %s)
                ON CONFLICT (time) 
                DO UPDATE SET total_usd = EXCLUDED.total_usd;
            """, (date, total_value))

            conn.commit()
            logger.info(f"✅ Saved portfolio value for {date}: ${total_value:.2f}")
            return True

        except Exception as e:
            logger.error(f"❌ Database save error: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_recent_values(self, days: int = 7):
        """Get recent portfolio values"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("""
                SELECT time, total_usd 
                FROM crypto_total 
                WHERE time >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY time DESC;
            """, (days,))

            return cursor.fetchall()

        except Exception as e:
            logger.error(f"❌ Database query error: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

