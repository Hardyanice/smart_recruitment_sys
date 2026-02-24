"""
Database setup script for AI Recruitment System.
Creates tables and populates with sample job postings.
"""

import sqlite3
import os
from datetime import datetime


DB_DIR = 'database'
DB_PATH = os.path.join(DB_DIR, 'recruitment.db')


def create_tables():
    """Create database tables."""
    # Ensure database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create applications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            email TEXT NOT NULL,
            resume_path TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            score REAL NOT NULL,
            decision TEXT NOT NULL,
            evaluation_details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        )
    """)
    
    # Create indexes for better query performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_applications_job_id 
        ON applications(job_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_applications_decision 
        ON applications(decision)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_applications_score 
        ON applications(score DESC)
    """)
    
    conn.commit()
    conn.close()
    
    print("✓ Database tables created successfully")


def add_sample_jobs():
    """Add sample job postings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if jobs already exist
    cursor.execute("SELECT COUNT(*) FROM jobs")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"✓ Database already has {count} jobs. Skipping sample data insertion.")
        conn.close()
        return
    
    # Sample job descriptions
    sample_jobs = [
        {
            "title": "Senior Python Developer",
            "description": """
We are looking for a Senior Python Developer to join our team.

Requirements:
- 5+ years of experience in Python development
- Strong experience with Django or Flask frameworks
- Experience with REST APIs and microservices architecture
- Knowledge of SQL databases (PostgreSQL, MySQL)
- Experience with cloud platforms (AWS, Azure, or GCP)
- Familiarity with Docker and Kubernetes
- Experience with CI/CD pipelines
- Strong understanding of software design patterns
- Excellent problem-solving skills
- Bachelor's degree in Computer Science or related field

Nice to Have:
- Experience with machine learning frameworks (TensorFlow, PyTorch)
- Knowledge of frontend technologies (React, Vue.js)
- Experience with message queues (RabbitMQ, Kafka)
- Open source contributions

Responsibilities:
- Design and develop scalable backend services
- Write clean, maintainable, and well-documented code
- Collaborate with cross-functional teams
- Mentor junior developers
- Participate in code reviews
- Optimize application performance
"""
        },
        {
            "title": "Machine Learning Engineer",
            "description": """
We are seeking a Machine Learning Engineer to build and deploy AI models.

Requirements:
- 3+ years of experience in machine learning
- Strong knowledge of Python and ML frameworks (TensorFlow, PyTorch, scikit-learn)
- Experience with deep learning and neural networks
- Understanding of NLP, computer vision, or recommendation systems
- Experience with data preprocessing and feature engineering
- Knowledge of SQL and NoSQL databases
- Familiarity with cloud ML platforms (AWS SageMaker, Azure ML, Google AI Platform)
- Experience with MLOps and model deployment
- Strong mathematical and statistical background
- Master's degree in Computer Science, AI, or related field

Nice to Have:
- Experience with large language models (LLMs)
- Knowledge of transformers and attention mechanisms
- Experience with distributed training
- Research publications in ML/AI

Responsibilities:
- Develop and train machine learning models
- Deploy models to production environments
- Monitor and improve model performance
- Collaborate with data scientists and engineers
- Research and implement new ML techniques
"""
        },
        {
            "title": "Full Stack Developer",
            "description": """
Looking for a Full Stack Developer to work on web applications.

Requirements:
- 3+ years of full stack development experience
- Frontend: React, Vue.js, or Angular
- Backend: Node.js, Python (Django/Flask), or Java (Spring)
- Experience with REST APIs and GraphQL
- Knowledge of SQL and NoSQL databases
- Understanding of responsive design and CSS frameworks
- Experience with version control (Git)
- Familiarity with Agile development methodologies
- Strong communication skills
- Bachelor's degree in Computer Science or related field

Nice to Have:
- Experience with TypeScript
- Knowledge of DevOps practices
- Experience with cloud platforms
- Mobile development experience (React Native, Flutter)

Responsibilities:
- Develop and maintain web applications
- Build responsive user interfaces
- Design and implement APIs
- Write unit and integration tests
- Collaborate with designers and product managers
- Optimize application performance
"""
        },
        {
            "title": "DevOps Engineer",
            "description": """
We need a DevOps Engineer to manage our infrastructure and deployment pipelines.

Requirements:
- 4+ years of DevOps experience
- Strong knowledge of Linux/Unix systems
- Experience with Docker and Kubernetes
- Proficiency in scripting (Bash, Python)
- Experience with CI/CD tools (Jenkins, GitLab CI, GitHub Actions)
- Knowledge of infrastructure as code (Terraform, CloudFormation)
- Experience with cloud platforms (AWS, Azure, GCP)
- Understanding of monitoring tools (Prometheus, Grafana, ELK)
- Experience with configuration management (Ansible, Chef, Puppet)
- Strong problem-solving skills

Nice to Have:
- Experience with service mesh (Istio, Linkerd)
- Knowledge of security best practices
- Experience with databases administration
- Certification in cloud platforms

Responsibilities:
- Design and maintain CI/CD pipelines
- Manage cloud infrastructure
- Implement monitoring and logging solutions
- Automate deployment processes
- Ensure system security and compliance
- Troubleshoot production issues
"""
        },
        {
            "title": "Data Scientist",
            "description": """
Seeking a Data Scientist to extract insights from data and build predictive models.

Requirements:
- 3+ years of experience in data science
- Strong knowledge of Python and data science libraries (pandas, numpy, scikit-learn)
- Experience with statistical analysis and hypothesis testing
- Knowledge of machine learning algorithms
- Experience with data visualization (Matplotlib, Seaborn, Plotly)
- Proficiency in SQL and database querying
- Understanding of A/B testing and experimental design
- Strong analytical and problem-solving skills
- Master's or PhD in Statistics, Mathematics, Computer Science, or related field

Nice to Have:
- Experience with big data technologies (Spark, Hadoop)
- Knowledge of deep learning frameworks
- Experience with cloud data platforms
- Business intelligence tools experience (Tableau, Power BI)

Responsibilities:
- Analyze large datasets to identify trends and patterns
- Build and validate predictive models
- Create data visualizations and reports
- Collaborate with business stakeholders
- Present findings to technical and non-technical audiences
- Develop data-driven solutions to business problems
"""
        },
        {
            "title": "Frontend Developer (React)",
            "description": """
Looking for a Frontend Developer specialized in React to build modern web applications.

Requirements:
- 3+ years of React development experience
- Strong knowledge of JavaScript (ES6+) and TypeScript
- Experience with React Hooks, Context API, and Redux
- Understanding of component lifecycle and state management
- Proficiency in HTML5, CSS3, and responsive design
- Experience with RESTful APIs and async/await
- Knowledge of modern build tools (Webpack, Vite)
- Familiarity with testing frameworks (Jest, React Testing Library)
- Experience with version control (Git)
- Strong attention to detail and UI/UX sensibility

Nice to Have:
- Experience with Next.js or Gatsby
- Knowledge of GraphQL and Apollo Client
- Experience with CSS-in-JS libraries (styled-components, Emotion)
- Understanding of web performance optimization
- Experience with design systems

Responsibilities:
- Develop responsive and interactive user interfaces
- Implement reusable React components
- Optimize application performance
- Collaborate with designers and backend developers
- Write clean and maintainable code
- Participate in code reviews
"""
        }
    ]
    
    # Insert sample jobs
    for job in sample_jobs:
        cursor.execute("""
            INSERT INTO jobs (title, description, created_at)
            VALUES (?, ?, ?)
        """, (job['title'], job['description'], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Added {len(sample_jobs)} sample jobs to database")


def main():
    """Run database setup."""
    print("\n" + "="*60)
    print("DATABASE SETUP - AI Recruitment System")
    print("="*60 + "\n")
    
    print("Setting up database...")
    create_tables()
    add_sample_jobs()
    
    print("\n" + "="*60)
    print("✓ Database setup complete!")
    print(f"  Database location: {DB_PATH}")
    print("="*60 + "\n")
    
    print("Next steps:")
    print("  1. Set up .env file with your OpenAI API key")
    print("  2. Run: flask run")
    print("  3. Open: http://localhost:5000")
    print()


if __name__ == '__main__':
    main()