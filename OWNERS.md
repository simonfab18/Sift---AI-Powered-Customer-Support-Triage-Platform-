# Ownership

This file defines the default maintainers for production-critical areas. Keep it updated when module ownership changes.

## Critical modules

| Area | Paths | Primary owner | Backup owner |
|---|---|---|---|
| Backend API and authorization | `apps/api/app/api`, `apps/api/app/services`, `apps/api/app/core` | Product Engineering | Product Engineering |
| Database models and migrations | `apps/api/app/models`, `apps/api/alembic` | Product Engineering | Product Engineering |
| Gmail integration and sync | `apps/api/app/integrations/gmail`, `apps/api/app/services/gmail_connection_service.py`, `apps/api/app/worker` | Product Engineering | Product Engineering |
| AI triage | `apps/api/app/integrations/gemini`, `apps/api/app/services/ai_triage_service.py` | Product Engineering | Product Engineering |
| Frontend product app | `apps/web/app`, `apps/web/components`, `apps/web/features` | Product Engineering | Product Engineering |
| Deployment and release controls | `.github/workflows`, `render.yaml`, `docker-compose.yml`, `docs/DEPLOYMENT.md`, `docs/ENVIRONMENT.md` | Product Engineering | Product Engineering |
| Security and secrets handling | `apps/api/app/core`, `apps/api/app/api/deps.py`, `docs/ENVIRONMENT.md` | Product Engineering | Product Engineering |

## Review expectations

- Changes to critical modules should be reviewed through a pull request before merge.
- Schema changes require an Alembic migration, migration rollback notes, and CI migration validation.
- Production environment changes require the staging values to be confirmed separately from production values.
- Gmail, Gemini, Supabase, Redis, and encryption secrets must live only in deployment secret stores or local ignored env files.
