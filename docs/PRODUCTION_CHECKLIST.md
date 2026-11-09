# SKLAT PRO — Production Deployment Checklist

## Prerequisites
- [ ] Python 3.13+ installed
- [ ] PostgreSQL 14+ (production) or SQLite (development)
- [ ] Nginx or Apache reverse proxy
- [ ] SSL certificate (Let's Encrypt or commercial)
- [ ] Domain name configured

## Environment Variables (Required in Production)
```bash
export DJANGO_SECRET_KEY="<generate-strong-64-char-key>"
export DJANGO_DEBUG="False"
export DJANGO_ALLOWED_HOSTS="yourdomain.com,www.yourdomain.com"
export DB_NAME="sklatpro"
export DB_USER="sklatpro"
export DB_PASSWORD="<strong-password>"
export DB_HOST="localhost"
export DB_PORT="5432"
```

## Deployment Steps
1. [ ] Clone repository
2. [ ] Create virtual environment: `python -m venv venv`
3. [ ] Install dependencies: `pip install -r requirements.txt`
4. [ ] Set environment variables (see above)
5. [ ] Run migrations: `python manage.py migrate`
6. [ ] Collect static files: `python manage.py collectstatic --noinput`
7. [ ] Create superuser: `python manage.py createsuperuser`
8. [ ] Seed SaaS data: `python manage.py seed_saas`
9. [ ] Configure Gunicorn/uWSGI
10. [ ] Configure Nginx reverse proxy
11. [ ] Test health check: `curl https://yourdomain.com/platform/health/`
12. [ ] Verify login works
13. [ ] Verify all modules accessible

## Post-Deployment
- [ ] Monitor logs for errors
- [ ] Verify backups running
- [ ] Test rate limiting
- [ ] Verify security headers present
- [ ] Check CSRF protection active
