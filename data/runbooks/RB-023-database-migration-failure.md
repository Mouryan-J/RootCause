# RB-023 — Database Migration Failure

**Service:** PostgreSQL / Alembic  
**Severity:** Critical  
**Tags:** database, migration, alembic, schema, postgres

## Symptoms
- Deploy fails with `alembic.exc.CommandError` or `sqlalchemy.exc.ProgrammingError`
- Application startup blocked: `Target database is not up to date`
- New code throwing `column "X" does not exist` in production
- Partial migration applied — database in inconsistent state

## Possible Causes
- Migration script has a bug (typo in column name, wrong data type)
- Migration requires acquiring a lock on a heavily-used table — times out
- Concurrent migration runs (multiple pods migrating simultaneously)
- Dependent migration missing from version history (merged branch skipped a revision)
- `NOT NULL` column added without default on table with existing rows

## Diagnostic Steps

```bash
# Check current migration state
alembic current

# Check migration history
alembic history --verbose

# Check if migrations are at head
alembic check

# Check Postgres locks during migration (from another session)
SELECT pid, wait_event_type, wait_event, query, state
FROM pg_stat_activity
WHERE wait_event IS NOT NULL;

# Check for broken migration state
alembic heads  # should show single head; multiple = branch divergence
```

## Remediation Steps

### Immediate
1. If migration is stuck due to a lock, identify and cancel the blocking query:
   ```sql
   SELECT pg_cancel_backend(<blocking_pid>);
   ```
2. If migration partially applied and broke things, roll back:
   ```bash
   alembic downgrade -1
   ```
3. If rollback is not possible (destructive migration), restore from backup and replay.

### Short-term
4. Fix the migration script bug and re-run:
   ```bash
   alembic upgrade head
   ```
5. For `NOT NULL` column without default — add with a default first:
   ```sql
   -- Step 1: add nullable column
   ALTER TABLE incidents ADD COLUMN new_col TEXT;
   -- Step 2: backfill
   UPDATE incidents SET new_col = 'default_value';
   -- Step 3: add NOT NULL constraint
   ALTER TABLE incidents ALTER COLUMN new_col SET NOT NULL;
   ```
6. Use migration locking to prevent concurrent runs:
   ```python
   # Acquire advisory lock before running migrations
   conn.execute("SELECT pg_advisory_lock(12345)")
   ```

### Long-term
7. Run migrations in a dedicated init container, not all app pods simultaneously.
8. Test migrations against a production-size database copy in staging.
9. Add migration check to CI: `alembic check` must pass before merge.

## Prevention
- Never add `NOT NULL` columns without a server default in a single migration step.
- Use `CONCURRENTLY` for index creation in migrations.
- Always test migration rollback (`alembic downgrade -1`) in staging.
