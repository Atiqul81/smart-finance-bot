import psycopg2
import logging
import os
from dotenv import load_dotenv
from contextlib import contextmanager
from datetime import date

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

DEFAULT_CATEGORIES = [
    "Food", "Transport", "Entertainment", "Groceries", "Utilities",
    "Medical Treatment", "Personal Care", "Education", "Gift/Donation",
    "Internet/Phone", "Rent", "Savings", "Investment", "Subscriptions",
    "Others"
]

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        yield conn
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        logging.exception("Database error occurred.")
        if conn:
            conn.rollback()
        raise error
    finally:
        if conn:
            conn.close()


def setup_database():
    """Sets up tables if not exists."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255)
                    );
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        UNIQUE (user_id, name)
                    );
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                        amount DECIMAL(10, 2) NOT NULL,
                        description TEXT,
                        date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS budgets (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                        amount DECIMAL(10, 2) NOT NULL,
                        period_month DATE NOT NULL DEFAULT DATE_TRUNC('month', CURRENT_DATE),
                        UNIQUE (user_id, category_id, period_month)
                    );
                """)
        logging.info("Database setup successful: Tables checked/created.")
    except Exception:
        logging.exception("FATAL: Could not set up database.")


def ensure_default_categories(user_id: int):
    """Insert default categories for a user if they don't exist."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for name in DEFAULT_CATEGORIES:
                    try:
                        cur.execute(
                            """
                            INSERT INTO categories (user_id, name)
                            VALUES (%s, %s)
                            ON CONFLICT (user_id, name) DO NOTHING
                            """,
                            (user_id, name)
                        )
                    except Exception:
                        logging.exception("Error seeding category %s for user %s", name, user_id)
    except Exception:
        logging.exception("Error ensuring default categories for user %s", user_id)


def current_period() -> date:
    from datetime import datetime
    now = datetime.now().date()
    return now.replace(day=1)


def get_or_create_category_id(cur, user_id, category_name: str) -> int:
    cur.execute("SELECT id FROM categories WHERE user_id = %s AND name = %s", (user_id, category_name))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO categories (user_id, name) VALUES (%s, %s) RETURNING id", (user_id, category_name))
    return cur.fetchone()[0]