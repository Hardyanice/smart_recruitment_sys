"""
Flask Application for AI Resume Screening System
Database-powered version with 2,277+ real job descriptions
"""

#-------
# Changed on 10/2 13:09
import sys
import os

# Folder containing app_updated.py (resume_jd_agent)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# smart_recruitment_system
# PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))


# For: from src....
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# For: from eye_movement_for_proctoring....
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

print("==== sys.path at startup ====")
for p in sys.path:
    print(p)
print("==============================")

#-------

from flask import Flask, json, render_template, request, redirect, url_for, flash, jsonify, session

# Import your Agent class
# Ensure the path is correct based on your project structure
# from Module2_Agentic_workflow.root_agent_updated import RecruitmentRootAgent

from werkzeug.utils import secure_filename
import os
from datetime import datetime
import logging
import traceback
import sqlite3


'''
# Calculate the absolute path to the 'eye_movement_for_proctoring' folder
# current_file_path = os.path.abspath(__file__) # Path to app_updated.py
# # Move up the required levels to reach the root 'Combined' or common parent
# project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
# module2_path = os.path.join(project_root, "eye_movement_for_proctoring", "Module2_Agentic_workflow")

# # Add both to sys.path
# if project_root not in sys.path:
#     sys.path.append(project_root)
# if module2_path not in sys.path:
#     sys.path.append(module2_path)

# Calculate absolute paths
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

# Path to the directory where 'sub_agents' folder is located
module2_dir = os.path.join(project_root, "eye_movement_for_proctoring", "Module2_Agentic_workflow")

# Add all required directories to sys.path
if project_root not in sys.path:
    sys.path.append(project_root)
if module2_dir not in sys.path:
    sys.path.append(module2_dir) # This fixes the 'sub_agents' error
'''

# Now use the full path relative to the newly added root
from eye_movement_for_proctoring.Module2_Agentic_workflow.root_agent_updated import RecruitmentRootAgent
import logging
# Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# Change this line in app_updated.py
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO to hide internal library logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Specifically silence LiteLLM if it still persists
logging.getLogger('lite_llm').setLevel(logging.WARNING)

# Disable all internal library debugging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('lite_llm').setLevel(logging.ERROR)

# Configure your simple format
logging.basicConfig(level=logging.INFO, format='%(message)s')

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

# from flask import request # Make sure this is imported at the top

# @app.route('/start_assessment')
# def start_assessment():
#     # 1. Get the name from the URL (?candidate_name=...)
#     candidate_name = request.args.get('candidate_name', 'Guest_Candidate')
#     job_id = request.args.get('job_id')
#     # 1. Fetch the specific JD from the database
#     job = get_job_by_id(job_id)
#     jd_text = job['description'] if job else "General Technical Role"


#     python_312_exe = r"D:\Christ University\Internship_6th_Sem\Machine Learning\resume-screening\Combined\eye_movement_for_proctoring\venv_312\Scripts\python.exe"
#     script_path = r"D:\Christ University\Internship_6th_Sem\Machine Learning\resume-screening\Combined\eye_movement_for_proctoring\Module2_Agentic_workflow\app_ui.py"
    
#     try:
#         # 2. Pass the candidate_name as an argument to the .py file
#         subprocess.Popen(
#             [python_312_exe, script_path, candidate_name, jd_text], 
#             cwd=os.path.dirname(script_path)
#         )
        
#         return "<h1>Assessment Started!</h1><p>Check your desktop for the full-screen window.</p>"
#     except Exception as e:
#         return f"Error: {str(e)}", 500

# ... [Keep your Database Functions and existing index/apply routes] ...

# Global dict to hold active agents


# Tracks question count: { "sess_key": integer_count }


# ============================================================
# ASSESSMENT & AGENTIC ROUTES
# ============================================================

# @app.route('/start_assessment')
# def start_assessment():
#     candidate_name = request.args.get('candidate_name', 'Guest')
#     job_id = request.args.get('job_id')
    
#     # 1. Fetch JD from DB
#     job = get_job_by_id(job_id)
#     jd_text = job['description'] if job else "Technical Role"

#     # 2. Initialize the RecruitmentRootAgent from Module 2
#     # This now runs within the Flask process, not a subprocess
#     try:
#         agent = RecruitmentRootAgent(candidate_id=candidate_name, job_desc=jd_text)
        
#         # 3. Store agent instance
#         sess_key = f"{candidate_name}_{job_id}_{datetime.now().strftime('%H%M%S')}"
#         active_assessment_sessions[sess_key] = agent
        
#         logger.info(f"Started assessment session for {candidate_name} (Session: {sess_key})")
        
#         return render_template('assessment.html', 
#                                candidate_name=candidate_name, 
#                                sess_key=sess_key)
#     except Exception as e:
#         logger.error(f"Failed to initialize Agent: {e}")
#         flash("Could not start assessment engine. Please try again.", "error")
#         return redirect(url_for('index'))
# Global dict to hold active agents

# --- GLOBAL BRUTE-FORCE TRACKERS ---
active_assessment_sessions = {}  # Holds the Agent objects
session_counters = {}           # Holds the current question number {sess_key: int}
session_questions = {}          # Holds the last question text {sess_key: str}
session_logs = {}               # Holds the history of evaluations {sess_key: list}

@app.route('/start_assessment')
def start_assessment():
    candidate_name = request.args.get('candidate_name', 'Guest')
    job_id = request.args.get('job_id')
    
    print(f"Candidate name: {candidate_name}")
    print(f"Job ID: {job_id}")
    job = get_job_by_id(job_id)
    jd_text = job['description'] if job else "Technical Role"
    
    # Initialize the Agent
    agent = RecruitmentRootAgent(candidate_id=candidate_name, job_desc=jd_text)
    
    # Create a consistent session key
    sess_key = f"{candidate_name}_{job_id}"
    active_assessment_sessions[sess_key] = agent
    
    # TRIGGER THE 3.10 GAZE SERVICE (Desktop background tracker)
    python_310_exe = os.path.join(PROJECT_ROOT, "eye_movement_for_proctoring", "gaze_service", "venv_310", "Scripts", "python.exe")
    gaze_script = os.path.join(PROJECT_ROOT, "eye_movement_for_proctoring", "gaze_service", "eye_tracker.py")
    
    try:
        # Pass the same sess_key to the background tracker
        subprocess.Popen([python_310_exe, gaze_script, "--session_id", sess_key])
        logger.info(f"✓ Gaze Tracker started for session: {sess_key}")
        # print("Gaze Tracker started for session")
    except Exception as e:
        logger.error(f"Failed to start gaze tracker: {e}")

    return render_template('assessment.html', candidate_name=candidate_name, sess_key=sess_key)

# @app.route('/api/get_next_question', methods=['POST'])
# def api_get_next_question():
#     data = request.get_json()
#     sess_key = data.get('sess_key')
#     agent = active_assessment_sessions.get(sess_key)
    
#     # Initialize count if not exists
#     if sess_key not in session_counters:
#         session_counters[sess_key] = 0

#     # Rule-based Limit Check
#     if session_counters[sess_key] >= agent.max_questions:
#         return jsonify({"question": "COMPLETED"})
        
#     question_text = agent.get_next_question()
    
#     # Increment immediately after successful generation
#     session_counters[sess_key] += 1

#     # 2. BRUTE-FORCE UPDATE: Store the text and increment count
#     session_questions[sess_key] = question_text
#     # session_counters[sess_key] = session_counters.get(sess_key, 0) + 1
    
#     print(f"[DEBUG] {sess_key} count incremented to: {session_counters[sess_key]}")
#     return jsonify({"question": question_text})

@app.route('/api/get_next_question', methods=['POST'])
def api_get_next_question():
    data = request.get_json()
    sess_key = data.get('sess_key')
    agent = active_assessment_sessions.get(sess_key)
    
    # Check current count BEFORE generating the next one
    current_count = session_counters.get(sess_key, 0)
    
    '''if current_count >= agent.max_questions:
        print(f"[STOP] Max questions ({agent.max_questions}) reached for {sess_key}.")
        
        # TRIGGER LOG EXPORT HERE
        agent.export_proctoring_json(session_logs.get(sess_key, []))
        
        return jsonify({"question": "COMPLETED"})'''

    # Updated by souhardya on  10/2 16:50 to add stop signal to stop camera after export
    #-----------------------------------------------------------------------------------
    
    if current_count >= agent.max_questions:
        print(f"[STOP] Max questions ({agent.max_questions}) reached for {sess_key}.")

        # 1. Tell eye tracker to stop
        gaze_log_dir = os.path.join(
            PROJECT_ROOT,
            "eye_movement_for_proctoring",
            "proctoring_logs",
            "gaze"
        )
        os.makedirs(gaze_log_dir, exist_ok=True)

        stop_file = os.path.join(gaze_log_dir, f"STOP_{sess_key}.flag")
        open(stop_file, "w").close()
        print(f"[GAZE] Stop signal created → {stop_file}")

        # 2. Export agent-side logs
        agent.export_proctoring_json(session_logs.get(sess_key, []))

        # 3. Trigger gaze analyzer AFTER tracker exits
        python_312_exe = os.path.join(
            PROJECT_ROOT,
            "eye_movement_for_proctoring",
            "venv_312",
            "Scripts",
            "python.exe"
        )
        analyzer_script = os.path.join(
            PROJECT_ROOT,
            "eye_movement_for_proctoring",
            "gaze_service",
            "gaze_analyzer.py"
        )

        # Changing on 12/2 from Popen to run so that we can wait for it to finish before showing the verdict

        subprocess.Popen([
            python_312_exe,
            analyzer_script,
            "--session_id",
            sess_key
        ])

        return jsonify({"question": "COMPLETED"})
    #-----------------------------------------------------
        
    question_text = agent.get_next_question()
    
    # Update Globals
    session_questions[sess_key] = question_text
    session_counters[sess_key] = current_count + 1
    
    return jsonify({"question": question_text})

# @app.route('/api/submit_answer', methods=['POST'])
# def api_submit_answer():
#     data = request.get_json()
#     sess_key = data.get('sess_key')
#     agent = active_assessment_sessions.get(sess_key)
    
#     if not agent:
#         return jsonify({"error": "Session not found"}), 404
    
#     user_answer = data.get('answer')
#     integrity_data = data.get('integrity_data', {})
    
#     # Map Web integrity to Agent integrity
#     mapped_integrity = {
#         "ikl_times": integrity_data.get('ikl_times', []),
#         "hold_times": integrity_data.get('hold_times', []),
#         "backspace_count": integrity_data.get('backspace_count', 0),
#         "switches": integrity_data.get('switches', 0),
#         "paste_count": integrity_data.get('paste_count', 0),
#         "prob": 0.0  # Placeholder that run_integrity_model will calculate
#     }
    
#     response_text = agent.process_evaluation(user_answer, mapped_integrity)
    
#     # 2. Rule-based Logging (Brute Force)
#     if sess_key not in session_logs:
#         session_logs[sess_key] = []
        
#     session_logs[sess_key].append({
#         "q_num": session_counters.get(sess_key),
#         "response": response_text
#     })

#     # 3. Print Logs for Question 1
#     print(f"\n---------- Logs from question {session_counters.get(sess_key)} -------------")
#     print(session_logs[sess_key][-1])

#     return jsonify({"status": "success", "response": response_text})

@app.route('/api/submit_answer', methods=['POST'])
def api_submit_answer():
    data = request.get_json()
    sess_key = data.get('sess_key')
    agent = active_assessment_sessions.get(sess_key)
    
    if not agent:
        return jsonify({"error": "Session not found"}), 404
    
    user_answer = data.get('answer')
    integrity_data = data.get('integrity_data', {})
    
    # Get current context from brute-force globals
    current_num = session_counters.get(sess_key, 0)
    last_q_text = session_questions.get(sess_key, "Technical Question")

    # Run Evaluation - we now expect back both the text and the ML results
    response_text, integrity_results = agent.process_evaluation(
        user_answer, 
        integrity_data, 
        current_num, 
        last_q_text
    )
    
    # Brute-Force Logging
    if sess_key not in session_logs:
        session_logs[sess_key] = []
        
    log_entry = {
        "q_num": current_num,
        "question": last_q_text,
        "answer": user_answer,
        "eval_response": response_text,
        "integrity": integrity_results
    }
    session_logs[sess_key].append(log_entry)

    # Print Logs to Terminal
    print(f"\n---------- Logs from question {current_num} -------------")
    print(f"Prob: {integrity_results.get('prob')}")
    print(f"Agent Response: {response_text}")
    print("-------------------------------------------------------\n")
    
    return jsonify({"status": "success", "response": response_text})

# added by souhardya on 10/2 18:20 for showing final verdict
#----------------------------------------------------------------------------------

@app.route("/verdict/<sess_key>")
def view_verdict(sess_key):

    verdict_dir = os.path.join(
        PROJECT_ROOT,
        "eye_movement_for_proctoring",
        "proctoring_logs",
        "final_verdicts"
    )

    verdict_path = os.path.join(
        verdict_dir,
        f"final_verdict_{sess_key}.json"
    )

    #-------------------------------------------------------------------------------
    # This is a brute-force check to see if the verdict file exists.
    print("PROJECT_ROOT:", PROJECT_ROOT)
    print("Looking in:", verdict_dir)
    print("Exists:", os.path.exists(verdict_dir))
    print("Files:", os.listdir(verdict_dir) if os.path.exists(verdict_dir) else "DIR NOT FOUND")
    print("Expected file:", verdict_path)
    print("File exists:", os.path.exists(verdict_path))
    #-------------------------------------------------------------------------------

    if not os.path.exists(verdict_path):
        return render_template(
            "verdict.html",
            error="Final verdict not found. Proctoring may still be processing.",
            sess_key=sess_key
        )

    with open(verdict_path, "r") as f:
        verdict_data = json.load(f)

    return render_template(
        "verdict.html",
        verdict=verdict_data,
        sess_key=sess_key
    )
#-----------------------------------------------------------------------------------------------

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

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("\n🚀 Assessment System Live at: http://localhost:5000\n")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    
    # Run the app
    # app.run(debug=True, host='0.0.0.0', port=5000)

