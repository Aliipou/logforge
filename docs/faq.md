# FAQ

## LogForge vs ELK Stack?
LogForge: 5 services, 2GB RAM, 5-minute setup. ELK: 6+ services, 8GB+ RAM, hours to set up. Use LogForge for < 1B logs/month.

## How to back up?
```bash
pg_dump -U logforge logforge | gzip > backup.sql.gz
```
