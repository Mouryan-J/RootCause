# PM-066 — Amazon

**Company:** Amazon  
**Category:** Conflicts  
**Source:** https://aws.amazon.com/message/101925/

## Incident Summary

A latent race condition in DynamoDB's DNS management left the regional endpoint `dynamodb.us-east-1.amazonaws.com` with an empty record. Two redundant "DNS Enactor" processes raced when one was unusually delayed; a second Enactor applied a newer plan and ran cleanup while the first overwrote the regional endpoint with a stale older plan, which the cleanup process then deleted. The DynamoDB outage cascaded into EC2 (DWFM "congestive collapse"), Network Load Balancer health-check flapping, and Lambda for ~15 hours.
