#!/usr/bin/env python3
"""
ARGUS - Database Initialization
Loads and executes the schema migration files
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create a connection to PostgreSQL"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("Error: DATABASE_URL not set in .env file")
        sys.exit(1)

    try:
        conn = psycopg2.connect(database_url)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def create_database_if_not_exists():
    """Create the argus database if it doesn't exist"""
    database_url = os.getenv('DATABASE_URL')

    # Parse the database URL to get connection params
    # Format: postgresql://user:password@host:port/database
    parts = database_url.replace('postgresql://', '').split('/')
    db_name = parts[-1]
    conn_string = f"postgresql://{parts[0]}"

    try:
        # Connect to the default 'postgres' database
        conn = psycopg2.connect(conn_string + '/postgres')
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cursor.fetchone()

        if not exists:
            print(f"Creating database '{db_name}'...")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(db_name)
            ))
            print(f"✓ Database '{db_name}' created successfully")
        else:
            print(f"Database '{db_name}' already exists")

        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"Error creating database: {e}")
        sys.exit(1)


def run_migration(conn, migration_file):
    """Execute a single migration file"""
    print(f"\nRunning migration: {migration_file.name}")
    print("=" * 60)

    try:
        with open(migration_file, 'r') as f:
            sql_content = f.read()

        cursor = conn.cursor()
        cursor.execute(sql_content)
        conn.commit()
        cursor.close()

        print(f"✓ Migration {migration_file.name} completed successfully")
        return True

    except psycopg2.Error as e:
        print(f"✗ Error running migration: {e}")
        conn.rollback()
        return False


def initialize_schema():
    """Main function to initialize the database schema"""
    print("\n" + "=" * 60)
    print("ARGUS - Database Initialization")
    print("=" * 60)

    # Step 1: Create database if needed
    create_database_if_not_exists()

    # Step 2: Connect to the database
    conn = get_db_connection()
    print("\n✓ Connected to database successfully")

    # Step 3: Find and run migration files
    migrations_dir = Path(__file__).parent.parent.parent / 'db' / 'migrations'

    if not migrations_dir.exists():
        print(f"\nError: Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    migration_files = sorted(migrations_dir.glob('*.sql'))

    if not migration_files:
        print("\nNo migration files found!")
        sys.exit(1)

    print(f"\nFound {len(migration_files)} migration(s)")

    # Run each migration
    for migration_file in migration_files:
        success = run_migration(conn, migration_file)
        if not success:
            print("\n✗ Migration failed. Stopping.")
            conn.close()
            sys.exit(1)

    # Step 4: Verify tables were created
    print("\n" + "=" * 60)
    print("Verifying schema...")
    print("=" * 60)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)

    tables = cursor.fetchall()
    print(f"\nCreated {len(tables)} tables:")
    for table in tables:
        print(f"  ✓ {table[0]}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("Database initialization complete! 🎯")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    initialize_schema()
