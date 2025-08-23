# REST API Reference

CodeDox provides a comprehensive REST API with automatic interactive documentation.

## Interactive API Documentation

FastAPI provides built-in interactive API documentation:

### Swagger UI
Visit **http://localhost:8000/docs** for the interactive Swagger UI where you can:
- Browse all available endpoints
- View request/response schemas
- Try out API calls directly in the browser
- See example responses

### ReDoc
Visit **http://localhost:8000/redoc** for the ReDoc documentation with:
- Clean, readable API documentation
- Detailed schema definitions
- Request/response examples

## Base URL
```
http://localhost:8000/api
```

## Authentication
Optional token-based authentication for remote deployments:
```bash
Authorization: Bearer <token>
```

## Key Endpoints

### Search
Search for code snippets across all libraries:
```bash
GET /api/search?q=authentication&limit=10
```

### Sources
List and manage documentation sources:
```bash
GET /api/sources
GET /api/sources/{source_id}
```

### Crawl Jobs
Manage documentation crawls:
```bash
GET /api/crawl-jobs
POST /api/crawl-jobs
GET /api/crawl-jobs/{job_id}
POST /api/crawl-jobs/{job_id}/cancel
POST /api/crawl-jobs/{job_id}/resume
```

### Upload
Upload markdown documentation:
```bash
POST /api/upload
```

### Statistics
Get system statistics:
```bash
GET /api/stats
```

## Using the API

### With curl
```bash
# Search for code
curl "http://localhost:8000/api/search?q=useState"

# Start a crawl
curl -X POST "http://localhost:8000/api/crawl-jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "React",
    "start_urls": ["https://react.dev/reference"],
    "max_depth": 2
  }'
```

### With Python
```python
import requests

# Search
response = requests.get("http://localhost:8000/api/search", 
                        params={"q": "authentication"})
results = response.json()

# Start crawl
crawl_data = {
    "name": "Next.js",
    "start_urls": ["https://nextjs.org/docs"],
    "max_depth": 2
}
response = requests.post("http://localhost:8000/api/crawl-jobs", 
                         json=crawl_data)
```

### With JavaScript
```javascript
// Search
const response = await fetch('http://localhost:8000/api/search?q=routing');
const results = await response.json();

// Start crawl
const crawlData = {
  name: 'Vue.js',
  start_urls: ['https://vuejs.org/guide/'],
  max_depth: 2
};
await fetch('http://localhost:8000/api/crawl-jobs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(crawlData)
});
```

## Error Handling

All errors follow a consistent format:
```json
{
  "detail": "Error message"
}
```

HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error