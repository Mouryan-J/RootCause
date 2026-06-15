# RB-025 — Dependency Version Conflict in Production

**Service:** Python Application  
**Severity:** High  
**Tags:** dependencies, python, pip, uv, versioning, packaging

## Symptoms
- `ImportError` or `AttributeError` in production that doesn't appear in staging
- `pkg_resources.ContextualVersionConflict` on startup
- LangChain / LangGraph API call fails because method signature changed in a patch update
- Application worked in CI but fails on the production Docker image

## Possible Causes
- Pinned dependency was updated by a transitive dependency
- `pyproject.toml` uses `>=` version bounds, allowing a breaking patch to be installed
- Docker image cached an old layer with different dependency versions
- `uv.lock` not committed — different installs on different machines
- Two packages requiring incompatible versions of the same transitive dependency

## Diagnostic Steps

```bash
# Check what versions are actually installed in production
kubectl exec -it <pod-name> -- uv pip list | grep -E 'langchain|openai|anthropic|pydantic'

# Compare with expected from lock file
cat uv.lock | grep -A 2 'name = "langchain"'

# Check for conflicts
kubectl exec -it <pod-name> -- uv pip check

# Reproduce locally with exact production packages
uv sync --frozen  # uses uv.lock exactly, no resolution
```

```python
# In application: print installed versions at startup for debugging
import importlib.metadata
for pkg in ['langchain', 'openai', 'anthropic', 'pydantic']:
    try:
        v = importlib.metadata.version(pkg)
        print(f"{pkg}=={v}")
    except importlib.metadata.PackageNotFoundError:
        print(f"{pkg}: NOT INSTALLED")
```

## Remediation Steps

### Immediate
1. Identify the specific package causing the error from the traceback.
2. Pin the working version explicitly in `pyproject.toml`:
   ```toml
   "langchain==0.3.1",  # pinned: 0.3.2 broke X
   ```
3. Rebuild and redeploy with the pinned version.

### Short-term
4. Commit `uv.lock` to git — this guarantees reproducible installs everywhere:
   ```bash
   git add uv.lock
   git commit -m "lock dependency versions"
   ```
5. Use `uv sync --frozen` in Dockerfile to install from lockfile exactly:
   ```dockerfile
   RUN uv sync --frozen --no-dev
   ```
6. Add CI step to check for lock file drift:
   ```bash
   uv lock --check  # fails if uv.lock is out of sync with pyproject.toml
   ```

### Long-term
7. Add weekly Dependabot / Renovate PR to update `uv.lock` in a controlled way.
8. Add integration tests that run against the actual dependency versions from `uv.lock`.
9. Review transitive dependency tree periodically: `uv tree`.

## Prevention
- Always commit `uv.lock` — it is the single source of truth for dependency versions.
- Always use `uv sync --frozen` in CI and Docker builds.
- Review dependency update PRs; never merge without running the test suite.
