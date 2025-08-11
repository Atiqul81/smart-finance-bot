import psycopg2
import logging
import os
from dotenv import load_dotenv
from contextlib import contextmanager

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

@contextmanager
def get_db_connection():
    """
    Provides a database connection using a context manager.
    This ensures the connection is always closed properly.
    """
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
            conn.rollback() # If error, rollback any changes
        raise error
    finally:
        if conn:
            conn.close()


def setup_database():
    """Sets up the database tables if they do not exist."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Create users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255)
                    );
                """)
                
                # Create categories table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        UNIQUE (user_id, name)
                    );
                """)

                # Create expenses table
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
                
                # Create budgets table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS budgets (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                        amount DECIMAL(10, 2) NOT NULL,
                        UNIQUE (user_id, category_id)
                    );
                """)
        logging.info("Database setup successful: Tables checked/created.")
    except Exception as error:
        logging.exception("FATAL: Could not set up database.")