# PM-002 — Amazon

**Company:** Amazon  
**Category:** Config Errors  
**Source:** https://aws.amazon.com/message/74876-2/

## Incident Summary

A configuration change in the Seoul region incorrectly removed the setting that specifies the minimum healthy hosts for the EC2 DNS resolver fleet, so the system fell back to a very low default. The fleet's healthy host count dropped and in-VPC DNS queries from EC2 instances failed for ~84 minutes until capacity was manually restored. AWS added semantic config validation and per-hour throttling on host removal as remediations.
