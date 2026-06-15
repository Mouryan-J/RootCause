# PM-055 — Amazon

**Company:** Amazon  
**Category:** Hardware/Power Failures  
**Source:** https://aws.amazon.com/message/656481/

## Incident Summary

Utility power was lost at a São Paulo AZ; during failover a breaker opened in front of one generator and a second generator independently failed mechanically, leaving the remaining healthy generators overloaded so they also shut down. The site's automated power-control system then malfunctioned, forcing operators to bring generators online manually. After power was restored, a network technician brought a device back up with a bad config that advertised an invalid route, degrading internet connectivity for both AZs in SA-EAST-1 for ~20 minutes.
