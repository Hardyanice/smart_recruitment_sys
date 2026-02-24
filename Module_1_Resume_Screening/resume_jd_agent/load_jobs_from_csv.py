"""
Load Job Descriptions from CSV into Database
Handles the 63K+ job descriptions from job_title_des.csv
"""

import sqlite3
import pandas as pd
import logging
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_database(db_path='jobs.db'):
    """Create SQLite database with jobs table"""
    
    logger.info(f"Creating database at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Drop existing table if exists
    cursor.execute('DROP TABLE IF EXISTS jobs')
    
    # Create jobs table
    cursor.execute('''
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Create index on title for faster searches
    cursor.execute('CREATE INDEX idx_title ON jobs(title)')
    cursor.execute('CREATE INDEX idx_active ON jobs(is_active)')
    
    conn.commit()
    conn.close()
    
    logger.info("✓ Database created successfully")


def load_jobs_from_csv(csv_path, db_path='jobs.db', batch_size=1000):
    """
    Load job descriptions from CSV into database
    
    Args:
        csv_path: Path to job_title_des.csv
        db_path: Path to SQLite database
        batch_size: Number of records to insert at once
    """
    
    logger.info(f"Loading jobs from {csv_path}")
    
    # Read CSV
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"✓ Loaded CSV with {len(df)} rows")
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return
    
    # Check columns
    logger.info(f"Columns: {df.columns.tolist()}")
    
    # Clean and prepare data
    df = df.rename(columns={'Job Title': 'title', 'Job Description': 'description'})
    
    # Keep only title and description columns
    df = df[['title', 'description']]
    
    # Drop rows with missing data
    original_count = len(df)
    df = df.dropna(subset=['title', 'description'])
    logger.info(f"Rows after removing nulls: {len(df)} (removed {original_count - len(df)})")
    
    # Clean text
    df['title'] = df['title'].astype(str).str.strip()
    df['description'] = df['description'].astype(str).str.strip()
    
    # Remove very short descriptions
    df = df[df['description'].str.len() > 50]
    logger.info(f"Rows after filtering short descriptions: {len(df)}")
    
    # Remove duplicates based on title + description
    df = df.drop_duplicates(subset=['title', 'description'])
    logger.info(f"Rows after removing duplicates: {len(df)}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert in batches
    total_inserted = 0
    errors = 0
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        
        try:
            batch.to_sql('jobs', conn, if_exists='append', index=False, 
                        dtype={'title': 'TEXT', 'description': 'TEXT'})
            total_inserted += len(batch)
            
            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"Progress: {total_inserted}/{len(df)} jobs inserted ({total_inserted/len(df)*100:.1f}%)")
                
        except Exception as e:
            logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
            errors += 1
    
    conn.commit()
    conn.close()
    
    logger.info("=" * 60)
    logger.info(f"✓ LOAD COMPLETE")
    logger.info(f"  Total inserted: {total_inserted}")
    logger.info(f"  Errors: {errors}")
    logger.info("=" * 60)
    
    return total_inserted


def get_job_stats(db_path='jobs.db'):
    """Get statistics about jobs in database"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total jobs
    cursor.execute('SELECT COUNT(*) FROM jobs')
    total = cursor.fetchone()[0]
    
    # Active jobs
    cursor.execute('SELECT COUNT(*) FROM jobs WHERE is_active = 1')
    active = cursor.fetchone()[0]
    
    # Top job titles
    cursor.execute('''
        SELECT title, COUNT(*) as count 
        FROM jobs 
        GROUP BY title 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    top_titles = cursor.fetchall()
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    print(f"Total jobs: {total:,}")
    print(f"Active jobs: {active:,}")
    print(f"\nTop 10 Job Titles:")
    for title, count in top_titles:
        print(f"  {title}: {count:,}")
    print("=" * 60 + "\n")


def search_jobs(keyword, db_path='jobs.db', limit=10):
    """Search for jobs by keyword"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, SUBSTR(description, 1, 200) as description_preview
        FROM jobs
        WHERE (title LIKE ? OR description LIKE ?)
        AND is_active = 1
        LIMIT ?
    ''', (f'%{keyword}%', f'%{keyword}%', limit))
    
    results = cursor.fetchall()
    conn.close()
    
    print(f"\nSearch results for '{keyword}':")
    print("-" * 60)
    for job_id, title, desc_preview in results:
        print(f"[{job_id}] {title}")
        print(f"    {desc_preview}...")
        print()
    
    return results


if __name__ == '__main__':
    import sys
    
    # Configuration
    CSV_PATH = r'data/raw/job_title_des.csv'
    DB_PATH = 'jobs.db'
    
    print("\n" + "=" * 60)
    print("JOB DATABASE LOADER")
    print("=" * 60)
    
    # Check if CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"✗ CSV file not found: {CSV_PATH}")
        sys.exit(1)
    
    # Create database
    create_database(DB_PATH)
    
    # Load jobs
    total = load_jobs_from_csv(CSV_PATH, DB_PATH, batch_size=1000)
    
    if total > 0:
        # Show statistics
        get_job_stats(DB_PATH)
        
        # Example searches
        print("\nExample searches:")
        search_jobs('Python', DB_PATH, limit=5)
        search_jobs('Machine Learning', DB_PATH, limit=5)
        
        print(f"\n✓ Database created at: {DB_PATH}")
        print(f"✓ Total jobs loaded: {total:,}")
    else:
        print("\n✗ No jobs loaded!")