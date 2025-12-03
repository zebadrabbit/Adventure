# Production Deployment Guide

## Overview
Adventure MUD can be deployed using Docker Compose for a complete production stack including PostgreSQL, Redis, and the web application.

## Prerequisites
- Docker and Docker Compose installed
- Git (for cloning the repository)
- Domain name (optional, for production use)

## Quick Start

### 1. Environment Setup

Copy the example environment file and configure for production:

```bash
cp .env.example .env
```

Edit `.env` and update these critical values:

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Update .env with generated key
SECRET_KEY=your-generated-key-here
POSTGRES_PASSWORD=strong-database-password-here
```

### 2. Build and Start Services

```bash
# Build the Docker image
docker-compose build

# Start all services (PostgreSQL, Redis, Web)
docker-compose up -d

# View logs
docker-compose logs -f web
```

The application will be available at `http://localhost:5000`

Database admin interface (Adminer) available at `http://localhost:8080`

### 3. Initialize Database

Database migrations run automatically on startup. To manually run migrations:

```bash
docker-compose exec web flask db upgrade
```

Seed the database with initial data:

```bash
docker-compose exec web flask seed-all
```

## Production Configuration

### Environment Variables

Key environment variables for production:

```bash
# Database
DATABASE_URL=postgresql://adventure:password@postgres:5432/adventure
POSTGRES_PASSWORD=strong-password

# Redis (for SocketIO scaling)
REDIS_URL=redis://redis:6379/0

# Flask
SECRET_KEY=your-secure-random-key
FLASK_ENV=production
FLASK_DEBUG=0

# Logging
LOG_LEVEL=INFO

# Application
MAX_CONTENT_LENGTH=16777216  # 16MB upload limit
```

### Reverse Proxy (Nginx)

For production, run behind Nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /socket.io {
        proxy_pass http://localhost:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL/TLS with Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

## Management Commands

Using the `manage.sh` script:

```bash
# Setup (create venv, install dependencies)
./manage.sh setup

# Start the application
./manage.sh start

# Stop the application
./manage.sh stop

# View logs (follow mode)
./manage.sh logs -f

# Run tests
./manage.sh test

# Database operations
./manage.sh db migrate  # Create new migration
./manage.sh db upgrade  # Apply migrations
./manage.sh db seed     # Seed database

# Code quality
./manage.sh lint        # Run ruff
./manage.sh format      # Run black
```

## Docker Commands

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f web
docker-compose logs -f postgres

# Restart a service
docker-compose restart web

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Execute commands in container
docker-compose exec web flask shell
docker-compose exec web python -m pytest

# Database backup
docker-compose exec postgres pg_dump -U adventure adventure > backup.sql

# Database restore
docker-compose exec -T postgres psql -U adventure adventure < backup.sql
```

## Monitoring and Logs

### Application Logs

Logs are written to `logs/` directory:

```bash
# View application logs
tail -f logs/error.log
tail -f logs/access.log

# Inside container
docker-compose exec web tail -f logs/error.log
```

### Database Logs

```bash
# PostgreSQL logs
docker-compose logs postgres
```

### Health Checks

The application includes health check endpoints:

```bash
# Application health
curl http://localhost:5000/health

# Database health (via Adminer)
open http://localhost:8080
```

## Scaling

To scale the web application:

```bash
# Run 4 web instances
docker-compose up -d --scale web=4

# Requires load balancer (nginx upstream)
```

Configure Nginx upstream:

```nginx
upstream adventure {
    server localhost:5000;
    server localhost:5001;
    server localhost:5002;
    server localhost:5003;
}

server {
    location / {
        proxy_pass http://adventure;
    }
}
```

## Backup and Recovery

### Database Backup

```bash
# Automated backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T postgres pg_dump -U adventure adventure | gzip > "backups/adventure_$DATE.sql.gz"
# Keep last 30 days
find backups/ -name "adventure_*.sql.gz" -mtime +30 -delete
EOF

chmod +x backup.sh

# Add to crontab for daily backups at 2 AM
0 2 * * * /path/to/backup.sh
```

### Restore from Backup

```bash
# Stop web service
docker-compose stop web

# Restore database
gunzip -c backups/adventure_20240101_020000.sql.gz | docker-compose exec -T postgres psql -U adventure adventure

# Restart web service
docker-compose start web
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U adventure -d adventure -c "SELECT 1;"
```

### Migration Issues

```bash
# Check migration status
docker-compose exec web flask db current

# View migration history
docker-compose exec web flask db history

# Downgrade one revision
docker-compose exec web flask db downgrade -1

# Upgrade to latest
docker-compose exec web flask db upgrade
```

### Permission Issues

```bash
# Fix file permissions (instance and logs directories)
docker-compose exec web chown -R adventure:adventure /app/instance /app/logs
```

## Security Checklist

- [ ] Change default passwords in `.env`
- [ ] Generate strong `SECRET_KEY`
- [ ] Set `FLASK_DEBUG=0` in production
- [ ] Run behind HTTPS (SSL/TLS)
- [ ] Configure firewall (only expose 80/443)
- [ ] Regular database backups
- [ ] Update dependencies regularly
- [ ] Monitor logs for suspicious activity
- [ ] Set up rate limiting
- [ ] Configure CORS properly (not `*`)

## Performance Tuning

### Gunicorn Workers

```bash
# In Dockerfile, adjust workers based on CPU cores
# Formula: (2 * CPU_CORES) + 1
--workers 4
```

### PostgreSQL

```bash
# In docker-compose.yml, add PostgreSQL tuning
environment:
  POSTGRES_SHARED_BUFFERS: 256MB
  POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB
  POSTGRES_WORK_MEM: 16MB
```

### Redis Cache

Configure Redis for session storage and caching:

```python
# In config.py
CACHE_TYPE = "redis"
CACHE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TYPE = "redis"
SESSION_REDIS = redis.from_url(os.getenv("REDIS_URL"))
```

## Updates and Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild container
docker-compose build web

# Apply migrations
docker-compose exec web flask db upgrade

# Restart
docker-compose restart web
```

### Update Dependencies

```bash
# Update requirements.txt
# Rebuild container
docker-compose build web
docker-compose up -d
```

## Support

For issues or questions:
- Check logs: `docker-compose logs -f web`
- Review documentation in `docs/`
- Check GitHub issues

## Additional Resources

- [Architecture Documentation](docs/architecture.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [WebSocket Events](docs/websocket_events.md)
- [Release Notes](docs/RELEASE_NOTES.md)
