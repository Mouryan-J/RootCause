# PM-103 — Amazon

**Company:** Amazon  
**Category:** Uncategorized  
**Source:** https://aws.amazon.com/message/65649/

## Incident Summary

Multiple SimpleDB storage nodes lost power simultaneously in one US-East data center. The lock service de-registered them rapidly, which spiked load and pushed handshake latencies above SimpleDB's too-aggressive handshake timeout. Healthy storage and metadata nodes failed their handshakes, removed themselves from the cluster, and couldn't rejoin because the metadata nodes that would authorize them had also taken themselves out. Recovery required manually raising the handshake timeout and restarting metadata nodes.
