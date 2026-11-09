# SKLAT PRO — Backup and Restore Guide

## What to Back Up
1. **Database** (most critical)
2. **Media files** (uploads, images, documents)
3. **Static files** (can be regenerated via `collectstatic`)
4. **Configuration** (settings, environment variables)

## Database Backup

### SQLite
```bash
cp db.sqlite3 db_backup_$(date +%Y%m%d_%H%M%S).sqlite3
```

### PostgreSQL
```bash
pg_dump -U sklatpro -d sklatpro -F c -f backup_$(date +%Y%m%d_%H%M%S).dump
```

## Media Backup
```bash
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/
```

## Full Backup Script
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp db.sqlite3 backups/db_$DATE.sqlite3
tar -czf backups/media_$DATE.tar.gz media/
echo "Backup complete: $DATE"
```

## Restore

### SQLite
```bash
cp backup.sqlite3 db.sqlite3
python manage.py migrate
```

### PostgreSQL
```bash
pg_restore -U sklatpro -d sklatpro backup.dump
python manage.py migrate
```

## Schedule Backups
Use cron (Linux) or Task Scheduler (Windows):
```
0 2 * * * /path/to/backup_script.sh
```

## Verify Backup Integrity
- Check file size is reasonable
- Test restore to a staging database
- Verify data counts match
