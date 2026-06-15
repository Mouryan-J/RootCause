# RB-024 — Configuration Drift After Deploy

**Service:** Application Configuration  
**Severity:** Medium–High  
**Tags:** configuration, deploy, env-vars, drift, secrets

## Symptoms
- Application behaves differently in production vs staging despite same code version
- `KeyError` or `ValidationError` on startup for a config key that exists in staging
- Feature that works locally fails in production — `settings.feature_flag` is wrong value
- Secrets reference correct key name but wrong version of the secret

## Possible Causes
- New environment variable added in code but not added to production secrets manager
- Secret rotation updated the value but not the reference (pointing to old version)
- Helm values file differs between environments (staging vs prod values)
- `.env.example` updated but production deployment not updated to match
- Config key name typo in production that works by accident with a default value

## Diagnostic Steps

```bash
# Check what env vars the running pod actually has
kubectl exec -it <pod-name> -- env | sort | grep -v SECRET | grep -v KEY

# Compare with expected from .env.example
cat .env.example | sort

# Check settings object at startup (add debug endpoint in dev)
curl http://localhost:8000/debug/settings  # if dev endpoint exists

# Diff production secrets vs expected
kubectl get secret rootcause-secrets -o json | jq '.data | keys'
```

```python
# Add a startup config validation check
from rootcause.core.config import get_settings

def validate_required_settings():
    s = get_settings()
    required = ['openai_api_key', 'anthropic_api_key', 'database_url']
    missing = [k for k in required if not getattr(s, k)]
    if missing:
        raise RuntimeError(f"Missing required config: {missing}")
```

## Remediation Steps

### Immediate
1. Identify the differing config key by comparing running env with `.env.example`.
2. Add the missing key to the production secrets manager and redeploy.
3. If wrong value is causing errors, update the secret immediately:
   ```bash
   kubectl create secret generic rootcause-secrets \
     --from-env-file=.env \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

### Short-term
4. Add config validation at startup (see code snippet above) — fail fast with clear error.
5. Add `.env.example` diff check to CI: fail the pipeline if a new config key is added to code without updating `.env.example`.

### Long-term
6. Use a config schema (pydantic-settings already provides this) — all required fields with no default will cause startup failure if missing.
7. Implement config-as-code: store all environment configs in git (without values), use secrets manager only for values.
8. Add post-deploy smoke test that validates every config key is populated.

## Prevention
- Always update `.env.example` alongside any new `Settings` field in a single PR.
- Add startup config validation — don't let a missing key cause a silent failure hours later.
- Review production secrets as part of deployment checklist.
