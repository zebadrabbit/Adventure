# Docker Setup Guide

## Quick Start with Docker

### 1. Copy the environment file
```bash
cp .env.example .env
```

### 2. Generate a secure secret key (Production only)
```bash
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env
```

### 3. Start the services
```bash
docker-compose up -d
```

This will:
- Start PostgreSQL on port 5432
- Run database migrations automatically
- Start the web server on http://localhost:5000

### 4. Create an admin user
```bash
docker-compose exec web python -c "
from app import app, db
from app.models.models import User
with app.app_context():
    u = User(username='admin', role='admin')
    u.set_password('admin')
    db.session.add(u)
    db.session.commit()
    print('Admin user created: admin/admin')
"
```

## Common Commands

### View logs
```bash
docker-compose logs -f web
docker-compose logs -f postgres
```

### Stop services
```bash
docker-compose down
```

### Stop and remove volumes (deletes database!)
```bash
docker-compose down -v
```

### Run migrations manually
```bash
docker-compose exec web alembic upgrade head
```

### Access PostgreSQL directly
```bash
docker-compose exec postgres psql -U adventure -d adventure_mud
```

### Run tests in Docker
```bash
docker-compose exec web pytest -v
```

## Environment Variables

### Required Variables

**DATABASE_URL** - PostgreSQL connection string
- Local Docker: `postgresql://adventure:adventure_dev_password@localhost:5432/adventure_mud`
- Production: `postgresql://username:password@hostname:5432/database_name`

**SECRET_KEY** - Flask secret key for sessions
- Development: Any string (not secure)
- Production: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### Optional Variables

**CORS_ALLOWED_ORIGINS** - CORS configuration (default: `*`)

**SOCKETIO_ASYNC_MODE** - SocketIO mode (default: auto-detect)
- Options: `gevent`, `threading`

**ENGINEIO_LOGGER** - Enable SocketIO logging (default: `1`)

**DUNGEON_ALLOW_HIDDEN_AREAS** - Enable hidden dungeon areas (default: `0`)

**DUNGEON_ENABLE_GENERATION_METRICS** - Track generation metrics (default: `1`)

**TEST_DATABASE_URL** - Separate database for tests (optional)

## Production Deployment

For production, update your `.env` file:

```bash
# Strong database password
DATABASE_URL=postgresql://adventure:STRONG_PASSWORD_HERE@postgres:5432/adventure_mud

# Secure secret key (generate new one!)
SECRET_KEY=your-generated-secret-key-here

# Restrict CORS to your domain
CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Disable debug logging
ENGINEIO_LOGGER=0
```

Also update `docker-compose.yml` to use the environment variable for the database password:

```yaml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

## Troubleshooting

### Database connection errors
```bash
# Check if PostgreSQL is ready
docker-compose exec postgres pg_isready -U adventure

# Restart PostgreSQL
docker-compose restart postgres
```

### Migration errors
```bash
# View migration history
docker-compose exec web alembic current

# Rollback one migration
docker-compose exec web alembic downgrade -1

# Upgrade to latest
docker-compose exec web alembic upgrade head
```

### Port already in use
If port 5000 or 5432 is already in use, edit `docker-compose.yml`:

```yaml
services:
  web:
    ports:
      - "8000:5000"  # Use port 8000 instead
```

## Development Workflow

### Making code changes
The application code is mounted as a volume, so changes are reflected immediately (you may need to restart the web container for some changes):

```bash
docker-compose restart web
```

### Installing new dependencies
```bash
# Add to requirements.txt, then:
docker-compose build web
docker-compose up -d web
```

### Database backups
```bash
# Backup
docker-compose exec postgres pg_dump -U adventure adventure_mud > backup.sql

# Restore
docker-compose exec -T postgres psql -U adventure adventure_mud < backup.sql
```
