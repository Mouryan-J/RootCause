# PM-035 — Keepthescore

**Company:** Keepthescore  
**Category:** Config Errors  
**Source:** https://web.archive.org/web/20201101133510/https://keepthescore.co/blog/posts/deleting_the_production_database/

## Incident Summary

Engineers deleted the production database by accident. Database is a managed database from DigitalOcean with backups once a day. 30 minutes after the disaster, it went back online, however 7 hours of scoreboard data was gone forever.
