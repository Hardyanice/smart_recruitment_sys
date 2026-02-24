"""
Flask Application for AI Resume Screening System
Database-powered version with 2,277+ real job descriptions
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import logging
import traceback
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import evaluation modules
try:
    from src.resume_evaluator import evaluate_resume
    from src.resume_extractor import extract_resume_text
    logger.info("✓ Successfully imported evaluation modules")
except ImportError as e:
    logger.error(f"✗ Failed to import modules: {e}")
    raise

app = Flask(__name__)
app.secret_key = 'change-this-to-a-secure-random-key-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['DATABASE'] = 'jobs.db'  # SQLite database path

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


def get_all_jobs(limit=None, offset=0, search=None):
    """Get all active jobs from database"""
    conn = get_db_connection()
    
    if search:
        query = '''
            SELECT id, title, description, created_at 
            FROM jobs 
            WHERE is_active = 1 
            AND (title LIKE ? OR description LIKE ?)
            ORDER BY created_at DESC
        '''
        params = (f'%{search}%', f'%{search}%')
        
        if limit:
            query += f' LIMIT {limit} OFFSET {offset}'
        
        jobs = conn.execute(query, params).fetchall()
    else:
        query = '''
            SELECT id, title, description, created_at 
            FROM jobs 
            WHERE is_active = 1 
            ORDER BY created_at DESC
        '''
        
        if limit:
            query += f' LIMIT {limit} OFFSET {offset}'
        
        jobs = conn.execute(query).fetchall()
    
    conn.close()
    
    # Convert to list of dicts
    return [dict(job) for job in jobs]


def get_job_by_id(job_id):
    """Get specific job by ID"""
    conn = get_db_connection()
    job = conn.execute(
        'SELECT id, title, description, created_at FROM jobs WHERE id = ? AND is_active = 1',
        (job_id,)
    ).fetchone()
    conn.close()
    
    return dict(job) if job else None


def get_job_count(search=None):
    """Get total number of active jobs"""
    conn = get_db_connection()
    
    if search:
        count = conn.execute(
            'SELECT COUNT(*) FROM jobs WHERE is_active = 1 AND (title LIKE ? OR description LIKE ?)',
            (f'%{search}%', f'%{search}%')
        ).fetchone()[0]
    else:
        count = conn.execute(
            'SELECT COUNT(*) FROM jobs WHERE is_active = 1'
        ).fetchone()[0]
    
    conn.close()
    return count


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Homepage with job listings"""
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '').strip()
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get jobs
    jobs = get_all_jobs(limit=per_page, offset=offset, search=search or None)
    total_jobs = get_job_count(search=search or None)
    total_pages = (total_jobs + per_page - 1) // per_page
    
    logger.info(f"Showing page {page} of {total_pages} ({len(jobs)} jobs)")
    
    return render_template(
        'index.html',
        jobs=jobs,
        page=page,
        total_pages=total_pages,
        total_jobs=total_jobs,
        search=search
    )


@app.route('/job/<int:job_id>')
def job_detail(job_id):
    """Show job details"""
    job = get_job_by_id(job_id)
    
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('job_detail.html', job=job)


@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply(job_id):
    """Handle job application"""
    
    # Get job from database
    job = get_job_by_id(job_id)
    
    if not job:
        logger.warning(f"Job ID {job_id} not found")
        flash('Job not found', 'error')
        return redirect(url_for('index'))
    
    # GET request: Show application form
    if request.method == 'GET':
        logger.info(f"Showing application form for job: {job['title']}")
        return render_template('apply.html', job=job)
    
    # POST request: Process application
    logger.info(f"Processing application for job: {job['title']}")
    
    try:
        # Extract form data
        candidate_name = request.form.get('candidate_name', '').strip()
        email = request.form.get('email', '').strip()
        
        logger.debug(f"Candidate: {candidate_name}, Email: {email}")
        
        # Validate required fields
        if not candidate_name or not email:
            logger.warning("Missing required fields")
            flash('Name and email are required', 'error')
            return render_template('apply.html', job=job)
        
        # Validate file upload
        if 'resume' not in request.files:
            logger.warning("No resume file in request")
            flash('Resume file is required', 'error')
            return render_template('apply.html', job=job)
        
        resume_file = request.files['resume']
        
        if resume_file.filename == '':
            logger.warning("Empty filename")
            flash('No file selected', 'error')
            return render_template('apply.html', job=job)
        
        if not resume_file.filename.lower().endswith('.pdf'):
            logger.warning(f"Invalid file type: {resume_file.filename}")
            flash('Only PDF files are allowed', 'error')
            return render_template('apply.html', job=job)
        
        # Save uploaded file
        filename = secure_filename(resume_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        logger.info(f"Saving resume to: {filepath}")
        resume_file.save(filepath)
        
        # Extract resume text
        logger.info("Extracting text from resume PDF...")
        resume_text = extract_resume_text(filepath)
        
        if not resume_text or len(resume_text.strip()) < 50:
            logger.error(f"Insufficient text extracted: {len(resume_text) if resume_text else 0} chars")
            flash('Could not extract text from resume. Please ensure it is a valid, text-based PDF.', 'error')
            os.remove(filepath)  # Clean up
            return render_template('apply.html', job=job)
        
        logger.info(f"✓ Extracted {len(resume_text)} characters from resume")
        logger.debug(f"Resume preview: {resume_text[:200]}...")
        
        # Get job description
        jd_text = job['description']
        logger.info(f"Job description length: {len(jd_text)} characters")
        
        # Evaluate resume (with detailed debugging)
        logger.info("=" * 60)
        logger.info("STARTING RESUME EVALUATION")
        logger.info("=" * 60)
        
        try:
            evaluation = evaluate_resume(
                resume_text=resume_text,
                jd_text=jd_text,
                debug=True  # Enable debug mode
            )
            
            logger.info("=" * 60)
            logger.info("EVALUATION COMPLETED")
            logger.info("=" * 60)
            logger.info(f"Evaluation result: {evaluation}")
            
            # Check if evaluation was successful
            if 'error' in evaluation:
                logger.error(f"Evaluation error: {evaluation['error']}")
                flash(f"Evaluation error: {evaluation['error']}", 'error')
                return render_template('apply.html', job=job)
            
            score = evaluation.get('score', 0)
            logger.info(f"FINAL SCORE: {score}")
            
            if score == 0:
                logger.warning("⚠ Score is 0 - possible evaluation issue!")
                logger.warning(f"Breakdown: {evaluation.get('breakdown', {})}")
                logger.warning(f"Feedback: {evaluation.get('feedback', [])}")
            
        except Exception as eval_error:
            logger.error(f"Evaluation failed with exception: {eval_error}")
            logger.error(traceback.format_exc())
            flash(f'Evaluation failed: {str(eval_error)}', 'error')
            return render_template('apply.html', job=job)
        
        # Transform evaluation results for template
        logger.info("Transforming results for template...")
        application_data = transform_for_template(
            evaluation=evaluation,
            candidate_name=candidate_name,
            email=email,
            job=job
        )
        
        logger.info(f"Application data prepared: score={application_data['score']}, decision={application_data['decision']}")
        
        # Optional: Keep or delete uploaded file
        # os.remove(filepath)  # Uncomment to delete after processing
        logger.info(f"Resume saved at: {filepath}")
        
        # Render results page
        logger.info("Rendering result.html")
        return render_template('result.html', application=application_data)
        
    except Exception as e:
        logger.error(f"Application processing error: {e}")
        logger.error(traceback.format_exc())
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('apply.html', job=job)


def transform_for_template(evaluation, candidate_name, email, job):
    """
    Transform evaluate_resume() output to match result.html template expectations.
    """
    logger.info("=" * 60)
    logger.info("TRANSFORMING DATA FOR TEMPLATE")
    logger.info("=" * 60)
    
    # Extract score (ensure it's a number)
    score = evaluation.get('score', 0)
    if isinstance(score, str):
        try:
            score = float(score)
        except:
            score = 0
    
    score = max(0, min(100, score))  # Clamp to 0-100
    logger.info(f"Score: {score}")
    
    # Determine decision based on threshold
    SHORTLIST_THRESHOLD = 50
    decision = 'Shortlisted' if score >= SHORTLIST_THRESHOLD else 'Rejected'
    logger.info(f"Decision: {decision} (threshold: {SHORTLIST_THRESHOLD})")
    
    # Extract breakdown
    breakdown = evaluation.get('breakdown', {})
    logger.debug(f"Breakdown: {breakdown}")
    
    # Extract matches and missing
    matched = evaluation.get('matched_requirements', [])
    partial = evaluation.get('partial_matches', [])
    missing = evaluation.get('missing_requirements', [])
    
    logger.info(f"Matched: {len(matched)}, Partial: {len(partial)}, Missing: {len(missing)}")
    
    # Build strengths list
    strengths = []
    
    # Add strong matches
    for match in matched[:5]:  # Top 5 strong matches
        req = match.get('requirement', 'Unknown requirement')
        pct = match.get('match_percentage', 0)
        concepts = match.get('matched_concepts', [])
        
        if concepts:
            concept_preview = ', '.join(concepts[:3])
            strengths.append(f"{req}: {pct}% match ({concept_preview})")
        else:
            strengths.append(f"{req}: {pct}% match")
    
    # If no strong matches, use semantic/coverage info
    if not strengths:
        semantic_score = breakdown.get('semantic_score', 0)
        coverage_score = breakdown.get('coverage_score', 0)
        
        if semantic_score > 40:
            strengths.append(f"Semantic relevance: {semantic_score}% - Shows related experience")
        if coverage_score > 30:
            strengths.append(f"Requirement coverage: {coverage_score}% - Some skills aligned")
        
        if not strengths:
            strengths.append("Basic qualifications present")
    
    logger.info(f"Strengths: {strengths}")
    
    # Build weaknesses list
    weaknesses = []
    
    # Add missing requirements
    for miss in missing[:5]:  # Top 5 missing
        req = miss.get('requirement', 'Unknown requirement')
        missing_concepts = miss.get('missing_concepts', [])
        
        if missing_concepts:
            concept_preview = ', '.join(missing_concepts[:3])
            weaknesses.append(f"Missing: {req} ({concept_preview})")
        else:
            weaknesses.append(f"Missing: {req}")
    
    # Add partial matches
    for part in partial[:3]:  # Top 3 partial
        req = part.get('requirement', 'Unknown requirement')
        pct = part.get('match_percentage', 0)
        missing_concepts = part.get('missing_concepts', [])
        
        if missing_concepts:
            concept_preview = ', '.join(missing_concepts[:2])
            weaknesses.append(f"Partial: {req} ({pct}% match, needs: {concept_preview})")
        else:
            weaknesses.append(f"Partial: {req} ({pct}% match)")
    
    # If no specific weaknesses, use general guidance
    if not weaknesses:
        if score < 60:
            weaknesses.append("Consider adding more relevant technical skills to your resume")
            weaknesses.append("Highlight specific technologies and frameworks mentioned in the job description")
        else:
            weaknesses.append("Minor improvements possible in skill presentation")
    
    logger.info(f"Weaknesses: {weaknesses}")
    
    # Build summary from feedback
    feedback_list = evaluation.get('feedback', [])
    summary = ' | '.join(feedback_list[:4]) if feedback_list else 'Evaluation completed.'
    logger.debug(f"Summary: {summary}")
    
    # Get recommendation
    recommendation = evaluation.get('recommendation', 'No recommendation available.')
    logger.debug(f"Recommendation: {recommendation}")
    
    # Build final application data
    application_data = {
        'id': abs(hash(f"{email}_{datetime.now().isoformat()}")) % 1000000,
        'candidate_name': candidate_name,
        'email': email,
        'job_id': job['id'],
        'job_title': job['title'],
        'score': int(round(score)),  # Integer for display
        'decision': decision,
        'created_at': datetime.now().isoformat(),
        'evaluation_details': {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'summary': summary,
            'recommendation': recommendation
        }
    }
    
    logger.info("=" * 60)
    logger.info("TEMPLATE DATA READY")
    logger.info(f"Final score: {application_data['score']}%")
    logger.info(f"Decision: {application_data['decision']}")
    logger.info("=" * 60)
    
    return application_data


@app.route('/search')
def search():
    """Search jobs"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return redirect(url_for('index'))
    
    return redirect(url_for('index', search=query))


@app.route('/api/stats')
def api_stats():
    """API endpoint for job statistics"""
    conn = get_db_connection()
    
    total_jobs = conn.execute('SELECT COUNT(*) FROM jobs WHERE is_active = 1').fetchone()[0]
    
    # Top job titles
    top_titles = conn.execute('''
        SELECT title, COUNT(*) as count 
        FROM jobs 
        WHERE is_active = 1
        GROUP BY title 
        ORDER BY count DESC 
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        'total_jobs': total_jobs,
        'top_titles': [{'title': row[0], 'count': row[1]} for row in top_titles]
    })


@app.route('/test')
def test():
    """Test endpoint to verify setup"""
    
    # Get job count
    job_count = get_job_count()
    
    # Get sample jobs
    sample_jobs = get_all_jobs(limit=5)
    
    html = f"""
    <h1>AI Resume Screening - System Check</h1>
    <ul>
        <li>Flask: ✓ Running</li>
        <li>Database: {'✓ Connected' if job_count > 0 else '✗ No jobs found'}</li>
        <li>Total jobs: {job_count:,}</li>
        <li>Templates: {'✓ Found' if os.path.exists('templates') else '✗ Missing'}</li>
        <li>Upload folder: {'✓ Created' if os.path.exists('uploads') else '✗ Missing'}</li>
    </ul>
    
    <h2>Sample Jobs:</h2>
    <ul>
    """
    
    for job in sample_jobs:
        html += f"<li><a href='/apply/{job['id']}'>{job['title']}</a> (ID: {job['id']})</li>"
    
    html += """
    </ul>
    <p><a href="/">Go to job listings</a></p>
    """
    
    return html

import subprocess
import os
# @app.route('/start_assessment')
# def start_assessment():
#     # 1. Define the EXACT path to your Python 3.12 executable
#     # This acts as the 'activated environment'
#     python_312_exe = r"D:\Christ University\Internship_6th_Sem\Machine Learning\resume-screening\Combined\eye_movement_for_proctoring\venv_312\Scripts\python.exe"
    
#     # 2. Define the path to the UI script
#     script_path = r"D:\Christ University\Internship_6th_Sem\Machine Learning\resume-screening\Combined\eye_movement_for_proctoring\Module2_Agentic_workflow\app_ui.py"
    
#     # 3. Launch it as a background process
#     try:
#         # We use Popen so Flask doesn't wait for the Tkinter window to close
#         # subprocess.Popen([python_312_exe, script_path], cwd=os.path.dirname(script_path))
#         # Pass the name from the application object
#         subprocess.Popen([python_312_exe, script_path, application['candidate_name']], cwd=os.path.dirname(script_path))
#         return "<h1>Assessment Started!</h1><p>The proctoring window should open on your desktop shortly.</p>"
#     except Exception as e:
#         logger.error(f"Failed to launch assessment: {e}")
#         return f"Error: {str(e)}", 500

from flask import request # Make sure this is imported at the top

@app.route('/start_assessment')
def start_assessment():
    # 1. Get the name from the URL (?candidate_name=...)
    candidate_name = request.args.get('candidate_name', 'Guest_Candidate')
    
    python_312_exe = r"D:\Christ University\Internship_6th_Sem\Machine Learning\resume-screening\Combined\eye_movement_for_proctoring\venv_312\Scripts\python.exe"
    script_path = r"D:\Christ University\Internship_6th_Sem\Machine Learning\resume-screening\Combined\eye_movement_for_proctoring\Module2_Agentic_workflow\app_ui.py"
    
    try:
        # 2. Pass the candidate_name as an argument to the .py file
        subprocess.Popen(
            [python_312_exe, script_path, candidate_name], 
            cwd=os.path.dirname(script_path)
        )
        
        return "<h1>Assessment Started!</h1><p>Check your desktop for the full-screen window.</p>"
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("STARTING AI RESUME SCREENING SYSTEM")
    logger.info("=" * 60)
    logger.info(f"Database: {app.config['DATABASE']}")
    logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"Max file size: {app.config['MAX_CONTENT_LENGTH'] / (1024*1024)} MB")
    
    # Check database
    try:
        job_count = get_job_count()
        logger.info(f"Jobs in database: {job_count:,}")
    except Exception as e:
        logger.error(f"Database error: {e}")
        logger.error("Make sure to run load_jobs_from_csv.py first!")
    
    logger.info("=" * 60)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)

