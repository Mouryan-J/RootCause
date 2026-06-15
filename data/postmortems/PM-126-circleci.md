# PM-126 — CircleCI

**Company:** CircleCI  
**Category:** Uncategorized  
**Source:** https://status.circleci.com/incidents/dcqb3fykhgvg

## Incident Summary

A staged Kubernetes upgrade of CircleCI's main production cluster left `kube-proxy` and `kubelet` at incompatible versions. The change between versions altered the format of `kube-proxy`'s `iptables` rulesets, so as pods churned and `Endpoints` objects changed, `kube-proxy`'s `Proxier.syncProxyRules()` (an `iptables-save` / `iptables-restore` read-modify-write) repeatedly hit "Sync failed" errors, leaving the per-node iptables in a corrupted state and silently breaking service-to-service routing across the cluster. Recovery required a full node-by-node cluster restart and triggered two follow-on incidents.
