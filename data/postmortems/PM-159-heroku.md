# PM-159 — Heroku

**Company:** Heroku  
**Category:** Uncategorized  
**Source:** https://status.heroku.com/incidents/642?postmortem

## Incident Summary

Having a system that requires scheduled manual updates resulted in an error which caused US customers to be unable to scale, stop or restart dynos, or route HTTP traffic, and also prevented all customers from being able to deploy.
