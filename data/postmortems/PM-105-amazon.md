# PM-105 — Amazon

**Company:** Amazon  
**Category:** Uncategorized  
**Source:** https://aws.amazon.com/message/061323/

## Incident Summary

As the Lambda Frontend fleet scaled in response to normal daily traffic growth, it crossed a capacity threshold within a single cell that had never been reached before, triggering a latent software defect that caused Execution Environments to be successfully allocated but never fully utilized. Lambda invocations failed in the affected cell, cascading into STS, EKS, EventBridge, Connect, and the AWS Management Console for several hours.
