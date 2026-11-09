# SKLAT PRO — Deployment Guide

## Tech Stack
- **Backend**: Django 5.2, Python 3.13
- **Database**: PostgreSQL 14+ (production), SQLite (development)
- **Frontend**: Django templates, Bootstrap Icons, CSS variables
- **Auth**: django-axes (brute-force protection)
- **Static**: Whitenoise or Nginx

## Quick Start (Development)
```bash
cd "Sklat pro"
python -m venv venv
venv\Scripts\activate          # Windows
pip install django django-axes
set DJANGO_DEBUG=True
python manage.py migrate
python manage.py runserver
```

## Production Setup

### 1. Gunicorn
```bash
pip install gunicorn
gunicorn warehouse_system.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### 2. Nginx Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /static/ {
        alias /path/to/sklatpro/staticfiles/;
    }
    location /media/ {
        alias /path/to/sklatpro/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Database (PostgreSQL)
```bash
createdb sklatpro
python manage.py migrate
```

### 4. Health Check
```bash
curl -u admin:password https://yourdomain.com/platform/health/
# Returns: {"database": "healthy", "application": "healthy", ...}
```

## Background Jobs
- Uses Python `threading` module (no Celery/Redis)
- Automation rules run in background threads
- AI insights computed on-demand with caching
