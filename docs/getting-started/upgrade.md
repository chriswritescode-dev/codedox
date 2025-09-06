# Upgrade Guide

This guide walks you through upgrading CodeDox to newer versions, including database migrations, dependency updates, and configuration changes.

## Before You Upgrade

### Prerequisites

- **Backup your data** - Always backup your database and configuration before upgrading
- **Check requirements** - Ensure your system meets the requirements for the new version
- **Review changelog** - Check the [CHANGELOG.md](https://github.com/chriswritescode-dev/codedox/blob/main/CHANGELOG.md) for breaking changes
- **Stop active crawls** - Ensure no crawl jobs are running during upgrade

### Creating Backups

#### Database Backup

```bash
# Backup PostgreSQL database
pg_dump -U postgres -h localhost codedox > codedox_backup_$(date +%Y%m%d).sql

# Or with custom format for faster restore
pg_dump -U postgres -h localhost -Fc codedox > codedox_backup_$(date +%Y%m%d).dump
```

#### Configuration Backup

```bash
# Backup configuration files
cp .env .env.backup
cp -r config config.backup
```

## Standard Upgrade Process

### 1. Stop All Services

```bash
# Stop the API server and web UI
# Press Ctrl+C in the terminal running the services

# For Docker users
docker-compose down
```

### 2. Update Code

```bash
# Fetch latest changes
git fetch origin

# For specific version
git checkout v0.2.8

# Or for latest main branch
git pull origin main
```

### 3. Update Dependencies

#### Python Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Update Python packages
pip install -r requirements.txt --upgrade

# Install any new Playwright browsers if needed
crawl4ai-setup
```

#### Frontend Dependencies

```bash
# Update Node.js packages
cd frontend
npm install
npm audit fix  # Fix any security vulnerabilities
cd ..
```

### 4. Run Database Migrations

```bash
# Check current migration status
python migrate.py status

# Apply pending migrations
python migrate.py

# If migrations fail, use force to continue
python migrate.py migrate --force
```

### 5. Update Configuration

Check for new environment variables in `.env.example`:

```bash
# Compare your .env with the example
diff .env .env.example

# Add any new required variables to your .env
nano .env
```

### 6. Restart Services

```bash
# Start the application
python cli.py serve

# Or for Docker
docker-compose up -d
```

### 7. Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Run a test search
python cli.py search "test query"

# Check the web UI at http://localhost:5173
```

## Version-Specific Upgrade Notes

### Upgrading to 0.2.8

**New Features:**
- Enhanced markdown search with fallback
- Toggle between code-only and enhanced search modes
- Improved search highlighting

**Database Changes:**
- New indexes for markdown content search
- Performance optimizations for full-text search

**Migration Steps:**
```bash
# This version adds markdown search capabilities
python migrate.py
```

### Upgrading to Future Versions

**GitHub Integration (Unreleased):**
- New GitHub repository processing features
- Support for private repositories
- Additional configuration for GitHub tokens

**Required Configuration:**
```bash
# Add to .env for GitHub features
GITHUB_TOKEN=your_github_token_here
```

## Docker Upgrade

### Upgrading Docker Installation

```bash
# Stop current containers
docker-compose down

# Pull latest images
docker-compose pull

# Rebuild custom images
docker-compose build --no-cache

# Start with new version
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Volume Considerations

```bash
# List volumes
docker volume ls

# Backup PostgreSQL volume
docker run --rm -v codedox_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

## Troubleshooting

### Common Issues

#### Migration Failures

```bash
# Check migration error details
python migrate.py status

# Reset specific migration
psql -U postgres -d codedox -c "DELETE FROM schema_migrations WHERE version = '007_add_markdown_fulltext_search';"

# Retry migration
python migrate.py
```

#### Dependency Conflicts

```bash
# Clear pip cache
pip cache purge

# Reinstall in clean environment
pip install -r requirements.txt --force-reinstall
```

#### Database Connection Issues

```bash
# Test database connection
psql -U postgres -h localhost -d codedox -c "SELECT version();"

# Check PostgreSQL service
sudo systemctl status postgresql
```

### Performance Issues After Upgrade

```bash
# Rebuild database indexes
psql -U postgres -d codedox -c "REINDEX DATABASE codedox;"

# Update statistics
psql -U postgres -d codedox -c "ANALYZE;"
```

## Rollback Procedures

### Code Rollback

```bash
# Check previous version tag
git tag -l

# Rollback to previous version
git checkout v0.2.5

# Restore Python dependencies
pip install -r requirements.txt

# Restore frontend dependencies
cd frontend && npm install && cd ..
```

### Database Rollback

```bash
# Restore from backup
psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS codedox;"
psql -U postgres -h localhost -c "CREATE DATABASE codedox;"
psql -U postgres -h localhost codedox < codedox_backup_20241231.sql

# Or with custom format
pg_restore -U postgres -h localhost -d codedox codedox_backup_20241231.dump
```

### Configuration Rollback

```bash
# Restore configuration
cp .env.backup .env
cp -r config.backup config
```

## Best Practices

1. **Test in Development First** - Always test upgrades in a development environment
2. **Read Release Notes** - Review all changes in the new version
3. **Incremental Upgrades** - Don't skip major versions
4. **Monitor After Upgrade** - Watch logs and performance metrics
5. **Document Custom Changes** - Keep track of any local modifications

## Getting Help

If you encounter issues during upgrade:

1. Check the [GitHub Issues](https://github.com/chriswritescode-dev/codedox/issues)
2. Review the [CHANGELOG](https://github.com/chriswritescode-dev/codedox/blob/main/CHANGELOG.md)
3. Join the community discussions
4. Report bugs with detailed upgrade logs

## Automated Upgrade Script

For convenience, you can use this script to automate the upgrade process:

```bash
#!/bin/bash
# save as upgrade.sh

echo "Starting CodeDox upgrade..."

# Backup
echo "Creating backups..."
pg_dump -U postgres -h localhost codedox > "backups/codedox_$(date +%Y%m%d_%H%M%S).sql"
cp .env ".env.backup.$(date +%Y%m%d_%H%M%S)"

# Update code
echo "Updating code..."
git pull origin main

# Update dependencies
echo "Updating dependencies..."
source .venv/bin/activate
pip install -r requirements.txt --upgrade
cd frontend && npm install && cd ..

# Run migrations
echo "Running migrations..."
python migrate.py

echo "Upgrade complete! Please restart services manually."
```

Make the script executable: `chmod +x upgrade.sh`