# PM-020 — GitHub

**Company:** GitHub  
**Category:** Config Errors  
**Source:** https://github.blog/news-insights/company-news/github-availability-report-february-2026/

## Incident Summary

A telemetry gap caused security policies to be auto-applied to backend storage accounts in GitHub's underlying compute provider, blocking access to critical VM metadata. All VM create/delete/reimage operations failed, taking out Actions hosted runners in every region, Codespaces, Copilot coding agent, CodeQL, Dependabot, GitHub Enterprise Importer, and Pages for ~5h53m.
