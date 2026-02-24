import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os


DB_PATH = os.path.join('database', 'recruitment.db')


def get_db_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    """Convert sqlite3.Row to dictionary."""
    return dict(zip(row.keys(), row)) if row else None


# ==================== JOB OPERATIONS ====================

def get_all_jobs() -> List[Dict]:
    """Get all jobs from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, description, created_at 
        FROM jobs 
        ORDER BY created_at DESC
    """)
    
    jobs = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    return jobs


def get_job_by_id(job_id: int) -> Optional[Dict]:
    """Get job by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, description, created_at 
        FROM jobs 
        WHERE id = ?
    """, (job_id,))
    
    job = dict_from_row(cursor.fetchone())
    conn.close()
    
    return job


def create_job(title: str, description: str) -> int:
    """Create a new job posting."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO jobs (title, description, created_at)
        VALUES (?, ?, ?)
    """, (title, description, datetime.now().isoformat()))
    
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return job_id


# ==================== APPLICATION OPERATIONS ====================

def save_application(
    candidate_name: str,
    email: str,
    resume_path: str,
    job_id: int,
    score: float,
    decision: str,
    evaluation_details: Dict = None
) -> int:
    """Save a new job application."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Serialize evaluation details to JSON
    details_json = json.dumps(evaluation_details) if evaluation_details else None
    
    cursor.execute("""
        INSERT INTO applications (
            candidate_name, email, resume_path, job_id,
            score, decision, evaluation_details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        candidate_name, email, resume_path, job_id,
        score, decision, details_json, datetime.now().isoformat()
    ))
    
    application_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return application_id


def get_application_by_id(application_id: int) -> Optional[Dict]:
    """Get application by ID with job details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            a.id,
            a.candidate_name,
            a.email,
            a.resume_path,
            a.score,
            a.decision,
            a.evaluation_details,
            a.created_at,
            j.id as job_id,
            j.title as job_title,
            j.description as job_description
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.id = ?
    """, (application_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    application = dict_from_row(row)
    
    # Parse evaluation details from JSON
    if application.get('evaluation_details'):
        try:
            application['evaluation_details'] = json.loads(application['evaluation_details'])
        except:
            application['evaluation_details'] = {}
    
    return application


def get_applications_by_job(job_id: int, decision: str = None) -> List[Dict]:
    """Get all applications for a specific job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if decision:
        cursor.execute("""
            SELECT 
                id, candidate_name, email, score, decision, created_at
            FROM applications
            WHERE job_id = ? AND decision = ?
            ORDER BY score DESC, created_at DESC
        """, (job_id, decision))
    else:
        cursor.execute("""
            SELECT 
                id, candidate_name, email, score, decision, created_at
            FROM applications
            WHERE job_id = ?
            ORDER BY score DESC, created_at DESC
        """, (job_id,))
    
    applications = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    return applications


def get_shortlisted_candidates(job_id: int = None) -> List[Dict]:
    """Get all shortlisted candidates, optionally filtered by job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if job_id:
        cursor.execute("""
            SELECT 
                a.id,
                a.candidate_name,
                a.email,
                a.score,
                a.resume_path,
                a.created_at,
                j.id as job_id,
                j.title as job_title
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.decision = 'Shortlisted' AND a.job_id = ?
            ORDER BY a.score DESC, a.created_at DESC
        """, (job_id,))
    else:
        cursor.execute("""
            SELECT 
                a.id,
                a.candidate_name,
                a.email,
                a.score,
                a.resume_path,
                a.created_at,
                j.id as job_id,
                j.title as job_title
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.decision = 'Shortlisted'
            ORDER BY a.score DESC, a.created_at DESC
        """)
    
    candidates = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    
    return candidates


def get_application_count_by_job(job_id: int) -> Dict[str, int]:
    """Get application statistics for a job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN decision = 'Shortlisted' THEN 1 ELSE 0 END) as shortlisted,
            SUM(CASE WHEN decision = 'Rejected' THEN 1 ELSE 0 END) as rejected
        FROM applications
        WHERE job_id = ?
    """, (job_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict_from_row(row) if row else {'total': 0, 'shortlisted': 0, 'rejected': 0}


def update_application_decision(application_id: int, decision: str) -> bool:
    """Update application decision (for manual review later)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE applications 
        SET decision = ?
        WHERE id = ?
    """, (decision, application_id))
    
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows_affected > 0


def delete_application(application_id: int) -> bool:
    """Delete an application (and associated resume file)."""
    # First get the application to delete the file
    application = get_application_by_id(application_id)
    
    if not application:
        return False
    
    # Delete the resume file if it exists
    if application.get('resume_path') and os.path.exists(application['resume_path']):
        try:
            os.remove(application['resume_path'])
        except:
            pass  # Continue even if file deletion fails
    
    # Delete from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM applications WHERE id = ?", (application_id,))
    
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows_affected > 0




def get_overall_statistics() -> Dict:
    """Get overall system statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT id) as total_jobs
        FROM jobs
    """)
    job_stats = cursor.fetchone()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_applications,
            SUM(CASE WHEN decision = 'Shortlisted' THEN 1 ELSE 0 END) as shortlisted,
            SUM(CASE WHEN decision = 'Rejected' THEN 1 ELSE 0 END) as rejected,
            AVG(score) as avg_score
        FROM applications
    """)
    app_stats = cursor.fetchone()
    
    conn.close()
    
    return {
        'total_jobs': job_stats[0] if job_stats else 0,
        'total_applications': app_stats[0] if app_stats else 0,
        'shortlisted': app_stats[1] if app_stats else 0,
        'rejected': app_stats[2] if app_stats else 0,
        'avg_score': round(app_stats[3], 2) if app_stats and app_stats[3] else 0
    }