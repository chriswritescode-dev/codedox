"""Test that duplicate detection is scoped to each source."""

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.database.content_check import find_duplicate_snippet_in_source
from src.database.models import CodeSnippet, CrawlJob, Document, UploadJob


class TestSourceScopedDuplicates:
    """Test suite for source-scoped duplicate detection."""

    def test_same_code_different_crawl_jobs(self, db: Session):
        """Test that same code can exist in different crawl jobs."""
        # Create two crawl jobs (e.g., React v18 and React v19)
        job1 = CrawlJob(
            id=uuid4(),
            name="React",
            version="v18",
            status="completed",
            domain="react.dev",
            start_urls=["https://react.dev/v18"],
        )
        job2 = CrawlJob(
            id=uuid4(),
            name="React",
            version="v19",
            status="completed",
            domain="react.dev",
            start_urls=["https://react.dev/v19"],
        )
        db.add_all([job1, job2])
        db.flush()

        # Create documents for each job
        doc1 = Document(
            url="https://react.dev/v18/hooks",
            title="React Hooks v18",
            crawl_job_id=job1.id,
            source_type="crawl",
        )
        doc2 = Document(
            url="https://react.dev/v19/hooks",
            title="React Hooks v19",
            crawl_job_id=job2.id,
            source_type="crawl",
        )
        db.add_all([doc1, doc2])
        db.flush()

        # Same code content
        code_content = "const [state, setState] = useState(0);"
        code_hash = hashlib.md5(code_content.encode()).hexdigest()

        # Check for duplicate in job1 - should not find any
        duplicate = find_duplicate_snippet_in_source(db, code_hash, doc1)
        assert duplicate is None

        # Add snippet to first job
        snippet1 = CodeSnippet(
            document_id=doc1.id,
            code_content=code_content,
            code_hash=code_hash,
            title="useState Example",
            description="Example of React useState hook",
            language="javascript",
        )
        db.add(snippet1)
        db.flush()

        # Check for duplicate in job1 again - should find snippet1
        duplicate = find_duplicate_snippet_in_source(db, code_hash, doc1)
        assert duplicate is not None
        assert duplicate.id == snippet1.id

        # Check for duplicate in job2 - should NOT find any (different source)
        duplicate = find_duplicate_snippet_in_source(db, code_hash, doc2)
        assert duplicate is None

        # Should be able to add same code to job2
        snippet2 = CodeSnippet(
            document_id=doc2.id,
            code_content=code_content,
            code_hash=code_hash,
            title="useState Example v19",
            description="Example of React useState hook in v19",
            language="javascript",
        )
        db.add(snippet2)
        db.flush()

        # Verify both snippets exist
        all_snippets = db.query(CodeSnippet).filter_by(code_hash=code_hash).all()
        assert len(all_snippets) == 2
        assert snippet1 in all_snippets
        assert snippet2 in all_snippets

    def test_same_code_crawl_vs_upload(self, db: Session):
        """Test that same code can exist in crawl job and upload job."""
        # Create a crawl job and an upload job
        crawl_job = CrawlJob(
            id=uuid4(),
            name="Vue.js",
            version="v3",
            status="completed",
            domain="vuejs.org",
            start_urls=["https://vuejs.org"],
        )
        upload_job = UploadJob(
            id=uuid4(),
            name="Vue.js Examples",
            version="custom",
            status="completed",
            source_type="upload",
        )
        db.add_all([crawl_job, upload_job])
        db.flush()

        # Create documents
        crawl_doc = Document(
            url="https://vuejs.org/guide/",
            title="Vue.js Guide",
            crawl_job_id=crawl_job.id,
            source_type="crawl",
        )
        upload_doc = Document(
            url="file://examples/vue-examples.md",
            title="Custom Vue Examples",
            upload_job_id=upload_job.id,
            source_type="upload",
        )
        db.add_all([crawl_doc, upload_doc])
        db.flush()

        # Same code content
        code_content = "const app = Vue.createApp({});"
        code_hash = hashlib.md5(code_content.encode()).hexdigest()

        # Add snippet to crawl job
        crawl_snippet = CodeSnippet(
            document_id=crawl_doc.id,
            code_content=code_content,
            code_hash=code_hash,
            title="Vue App Creation",
            language="javascript",
        )
        db.add(crawl_snippet)
        db.flush()

        # Check for duplicate in upload job - should NOT find any
        duplicate = find_duplicate_snippet_in_source(db, code_hash, upload_doc)
        assert duplicate is None

        # Add same code to upload job
        upload_snippet = CodeSnippet(
            document_id=upload_doc.id,
            code_content=code_content,
            code_hash=code_hash,
            title="Custom Vue Example",
            language="javascript",
        )
        db.add(upload_snippet)
        db.flush()

        # Verify both exist
        all_snippets = db.query(CodeSnippet).filter_by(code_hash=code_hash).all()
        assert len(all_snippets) == 2

    def test_duplicate_within_same_source(self, db: Session):
        """Test that duplicates are still prevented within same source."""
        # Create a crawl job
        job = CrawlJob(
            id=uuid4(),
            name="Angular",
            version="v15",
            status="completed",
            domain="angular.io",
            start_urls=["https://angular.io"],
        )
        db.add(job)
        db.flush()

        # Create two documents in the same job
        doc1 = Document(
            url="https://angular.io/guide/components",
            title="Components Guide",
            crawl_job_id=job.id,
            source_type="crawl",
        )
        doc2 = Document(
            url="https://angular.io/tutorial/components",
            title="Components Tutorial",
            crawl_job_id=job.id,
            source_type="crawl",
        )
        db.add_all([doc1, doc2])
        db.flush()

        # Same code content
        code_content = "@Component({ selector: 'app-root' })"
        code_hash = hashlib.md5(code_content.encode()).hexdigest()

        # Add snippet to first document
        snippet1 = CodeSnippet(
            document_id=doc1.id,
            code_content=code_content,
            code_hash=code_hash,
            title="Component Decorator",
            language="typescript",
        )
        db.add(snippet1)
        db.flush()

        # Check for duplicate in second document of SAME job - should find it
        duplicate = find_duplicate_snippet_in_source(db, code_hash, doc2)
        assert duplicate is not None
        assert duplicate.id == snippet1.id

        # Try to query all snippets with this hash - should only be one
        all_snippets = db.query(CodeSnippet).filter_by(code_hash=code_hash).all()
        assert len(all_snippets) == 1

    def test_orphan_documents(self, db: Session):
        """Test duplicate detection for documents without job association."""
        # Note: Documents must have either crawl_job_id or upload_job_id
        # So we'll test with upload documents instead
        upload_job = UploadJob(
            id=uuid4(),
            name="Manual Upload",
            source_type="upload",
            status="completed",
        )
        db.add(upload_job)
        db.flush()
        
        # Create two documents in same upload job
        doc1 = Document(
            url="https://example.com/doc1",
            title="Upload Doc 1",
            source_type="upload",
            upload_job_id=upload_job.id,
        )
        doc2 = Document(
            url="https://example.com/doc2",
            title="Upload Doc 2",
            source_type="upload",
            upload_job_id=upload_job.id,
        )
        db.add_all([doc1, doc2])
        db.flush()

        # Verify they're in the same upload job
        assert doc1.crawl_job_id is None
        assert doc1.upload_job_id == upload_job.id
        assert doc2.crawl_job_id is None  
        assert doc2.upload_job_id == upload_job.id

        # Same code content
        code_content = "console.log('test');"
        code_hash = hashlib.md5(code_content.encode()).hexdigest()

        # Add snippet to first orphan
        snippet1 = CodeSnippet(
            document_id=doc1.id,
            code_content=code_content,
            code_hash=code_hash,
            title="Test Log",
            language="javascript",
        )
        db.add(snippet1)
        db.flush()

        # Check for duplicate in second document of same upload job - should find it
        duplicate = find_duplicate_snippet_in_source(db, code_hash, doc2)
        assert duplicate is not None
        assert duplicate.id == snippet1.id

    def test_different_versions_same_library(self, db: Session):
        """Test that different versions of same library can have duplicate code."""
        # Create jobs for different versions of the same library
        versions = ["v1.0", "v1.5", "v2.0"]
        jobs = []
        docs = []

        for version in versions:
            job = CrawlJob(
                id=uuid4(),
                name="Express.js",
                version=version,
                status="completed",
                domain="expressjs.com",
                start_urls=[f"https://expressjs.com/{version}"],
            )
            jobs.append(job)
            db.add(job)

        db.flush()

        # Create documents for each version
        for i, job in enumerate(jobs):
            doc = Document(
                url=f"https://expressjs.com/{versions[i]}/api",
                title=f"Express API {versions[i]}",
                crawl_job_id=job.id,
                source_type="crawl",
            )
            docs.append(doc)
            db.add(doc)

        db.flush()

        # Common code that might exist in all versions
        code_content = "app.get('/', (req, res) => { res.send('Hello World'); });"
        code_hash = hashlib.md5(code_content.encode()).hexdigest()

        # Add the same code to all versions
        snippets = []
        for i, doc in enumerate(docs):
            # Check that no duplicate exists yet for this source
            duplicate = find_duplicate_snippet_in_source(db, code_hash, doc)
            assert duplicate is None

            snippet = CodeSnippet(
                document_id=doc.id,
                code_content=code_content,
                code_hash=code_hash,
                title=f"Hello World Example {versions[i]}",
                language="javascript",
            )
            snippets.append(snippet)
            db.add(snippet)
            db.flush()

        # Verify all three snippets exist
        all_snippets = db.query(CodeSnippet).filter_by(code_hash=code_hash).all()
        assert len(all_snippets) == 3

        # Each should be in a different source
        job_ids = set()
        for snippet in all_snippets:
            doc = db.query(Document).filter_by(id=snippet.document_id).first()
            job_ids.add(doc.crawl_job_id)

        assert len(job_ids) == 3  # Three different sources