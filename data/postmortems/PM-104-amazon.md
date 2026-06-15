# PM-104 — Amazon

**Company:** Amazon  
**Category:** Uncategorized  
**Source:** https://aws.amazon.com/message/17908/

## Incident Summary

A new failover-optimization protocol had been enabled in network device OS for 8 months without issue. A customer traffic pattern produced packets matching a very specific signature that triggered a latent defect in the OS, causing devices in one Direct Connect network layer to fail. Failed devices weren't automatically removed from service, so engineers manually drained them, only for additional devices to fail with the same bug. Disabling the new protocol restored Direct Connect to Tokyo after ~6 hours.
