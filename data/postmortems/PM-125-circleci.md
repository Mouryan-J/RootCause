# PM-125 — CircleCI

**Company:** CircleCI  
**Category:** Uncategorized  
**Source:** https://discuss.circleci.com/t/postmortem-may-21-2021-delay-in-starting-docker-jobs-machine-remote-docker-environments-blocked/40274

## Incident Summary

A routine RabbitMQ upgrade from 3.8.9 to 3.8.16 introduced a 15-minute consumer ack timeout that the changelog described as scoped to quorum queues but actually applied to all queue types. Consumers on the VM-destroyer queue gradually got their channels closed until the queue had zero consumers, so VMs in one region stopped being deleted; this eventually backed up VM creation and blocked Docker, machine, Windows, Mac, Arm, GPU, and remote-Docker jobs for ~12 hours.
