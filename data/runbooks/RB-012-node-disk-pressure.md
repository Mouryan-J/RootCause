# RB-012 — Node Disk Pressure

**Service:** Kubernetes Node  
**Severity:** High  
**Tags:** kubernetes, disk, storage, node, eviction

## Symptoms
- `kubectl get nodes` shows `DiskPressure=True` condition
- Pods begin getting evicted (`kubectl get events | grep Evicted`)
- New pods stuck in `Pending` — scheduler avoids the pressured node
- Application logs show `No space left on device` errors

## Possible Causes
- Container logs not rotated, consuming `/var/log` space
- Large container images filling the image layer cache
- Application writing logs or data to the container filesystem instead of a PVC
- Temporary files not cleaned up (e.g., `/tmp`, model download cache)
- Core dump files from crashed processes

## Diagnostic Steps

```bash
# Check disk usage on node (via debug pod or node SSH)
kubectl debug node/<node-name> -it --image=busybox -- df -h

# Find largest directories
kubectl debug node/<node-name> -it --image=busybox -- du -sh /host/* 2>/dev/null | sort -rh | head -20

# Check docker/containerd storage
kubectl debug node/<node-name> -it --image=busybox -- du -sh /host/var/lib/containerd

# Check log sizes
kubectl debug node/<node-name> -it --image=busybox -- du -sh /host/var/log/pods/*
```

```bash
# Via node SSH if accessible
df -h
du -sh /var/lib/docker/* | sort -rh | head -10
journalctl --disk-usage
```

## Remediation Steps

### Immediate
1. Clean up unused container images:
   ```bash
   # On the node:
   crictl rmi --prune
   # or for Docker:
   docker system prune -af
   ```
2. Remove large log files (back them up first if needed):
   ```bash
   find /var/log/pods -name "*.log" -size +100M -delete
   ```
3. Clear temp files:
   ```bash
   find /tmp -type f -atime +1 -delete
   ```

### Short-term
4. Configure `logrotate` or containerd log rotation:
   ```json
   // /etc/containerd/config.toml
   [plugins."io.containerd.grpc.v1.cri".containerd]
     max_container_log_line_size = 16384
   ```
5. Set log rotation in kubelet config:
   ```yaml
   containerLogMaxSize: "50Mi"
   containerLogMaxFiles: 5
   ```
6. Move application data writes to PVC, not container filesystem.

### Long-term
7. Add Prometheus alert: `node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.15`.
8. Add node auto-cleanup DaemonSet to prune old images on a schedule.
9. Right-size node root volume based on 30-day observed disk growth trend.

## Prevention
- Configure log rotation before deploying any workload.
- Never write application data to the container root filesystem.
- Alert at 85% disk usage with enough lead time to act before eviction begins.
