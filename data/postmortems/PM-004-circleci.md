# PM-004 — CircleCI

**Company:** CircleCI  
**Category:** Config Errors  
**Source:** https://discuss.circleci.com/t/post-incident-report-april-4-2025-circleci-ui-loading-build-triggering-issues/53208

## Incident Summary

An IAM-role gap permitted out-of-band changes to AWS WAF outside of CircleCI's Terraform pipeline; an operator performing what they believed were read-only investigation actions modified WAF in a way that began blocking legitimate traffic to the `api.circleci.com` and `circleci.com` CloudFront distributions. Because the change wasn't recorded in Terraform, responders deprioritized WAF as a suspect and chased CORS errors and recent deploys until automated drift detection surfaced the discrepancy.
