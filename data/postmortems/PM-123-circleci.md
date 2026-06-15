# PM-123 — CircleCI

**Company:** CircleCI  
**Category:** Uncategorized  
**Source:** https://web.archive.org/web/20180121023549/http://circleci.com/blog/mongohq-security-incident-response/

## Incident Summary

CircleCI's database provider, MongoHQ, was breached on October 27, 2013, and CircleCI's MongoDB was among the databases accessed; CircleCI was holding GitHub OAuth tokens, Heroku API tokens, AWS IAM keys, and SSH deploy/user keys for customers in that database. On notification, CircleCI shut down the site and all builds, then worked with GitHub, Heroku, and AWS to revoke every OAuth token, API token, IAM key, and SSH key it had handed out, and cycled all of its own keys and caches.
