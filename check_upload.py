from src.database import get_db_manager
from src.database.models import CodeSnippet, Document, UploadJob

db = get_db_manager()
session = db.get_session()

# Get the most recent upload job
job = session.query(UploadJob).filter_by(id='c2356571-cfa6-4adb-83c3-0900cd65280b').first()
if job:
    print(f'Job: {job.name}')
    print(f'Status: {job.status}')
    print(f'Error: {job.error_message}')

    # Get documents
    docs = session.query(Document).filter_by(upload_job_id=job.id).all()
    print(f'Documents: {len(docs)}')

    for doc in docs:
        snippets = session.query(CodeSnippet).filter_by(document_id=doc.id).all()
        print(f'  - {doc.title}: {len(snippets)} snippets')
        for snippet in snippets[:3]:  # Show first 3
            print(f'    - {snippet.title} ({snippet.language})')
else:
    print("Job not found")

session.close()
