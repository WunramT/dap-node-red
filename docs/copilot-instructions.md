# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


# Project Setup

Repository: PomocAI (Full-Stack: FastAPI + Vue + PostgreSQL)

Environments: dev via podman-compose.dev.yml; prod via Jenkins/GitLab CI + Docker

Primary languages: Python, TypeScript/Vue, SQL, YAML

# Tech Stack

Backend: FastAPI 0.115, Python 3.13, SQLAlchemy 2.0, Alembic 1.17, Uvicorn 0.34

Frontend: Vue 3.5, Vuetify 3.10, TypeScript 5.9, Vite 7.1

DB: PostgreSQL 17 (Alpine)

Tooling: Node 22, Python 3.13, Podman (dev) / Docker (prod), Git >= 2.40

# Golden Rules

DO: ask for a plan before changing files; then implement; then self-check; then commit

DO: use /clear when switching tasks to keep context tight

DO: prefer single-purpose commits, conventional messages, rebase before merge

DO NOT: modify .env, secrets, or production configs without explicit instruction

DO NOT: run destructive DB ops outside podman-compose.dev.yml network

# Commands

## Podman (dev)

Up: podman compose -f docker-compose.dev.yml up -d

Down: podman compose -f docker-compose.dev.yml down

Logs (all): podman compose -f docker-compose.dev.yml logs -f

Logs (svc): podman compose -f docker-compose.dev.yml logs -f backend|frontend|postgres

Shell: podman compose -f docker-compose.dev.yml exec backend|frontend|postgres bash

## Database

psql: podman compose -f docker-compose.dev.yml exec postgres psql -U dev_user -d app_db

readiness: pg_isready -h localhost -p 5432 -U dev_user

migrate up: podman compose -f docker-compose.dev.yml exec backend bash -c "cd /app && alembic -c migrations/alembic.ini upgrade head"

new revision: podman compose -f docker-compose.dev.yml exec backend bash -c "cd /app && alembic -c migrations/alembic.ini revision --autogenerate -m 'msg'"

## Backend

deps: pip install -r requirements.txt

dev server: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

lint/format/test: black backend/ && pylint backend/ && pytest

## Frontend

install: cd frontend && npm install

dev: npm run dev -- --host 0.0.0.0

build/preview: npm run build | npm run preview

quality: npm run type-check && npm run lint

## Git

status/history: git status | git log --oneline -n 10

rebase: git fetch origin && git rebase origin/main

diff: git diff origin/main

# Style Guides

## Python

PEP 8, type hints everywhere, 100 char lines, f-strings, stdlib -> third-party -> local imports

Use context managers; SQLAlchemy declarative models; docstrings on public API

Async where possible (async def); use Pydantic models for request/response schemas

## TypeScript/Vue

Strict TS (no implicit any), <script setup>, Props/Emits typed, Composition API, Vuetify consistently

## SQL

snake_case identifiers; CTEs for complex logic; index hot paths; migrations via Alembic only

## YAML

2-space indent, lowercase keys, descriptive service names, comment non-obvious configs

# Testing

Backend: pytest in backend/tests/, min coverage 85%, fixtures for DB session, mock external calls

Frontend: Vitest + @vue/test-utils for components, Pinia actions, API services

DB: isolated test DB; run alembic upgrade head before tests; cleanup per test

Integration: E2E Frontend -> Backend -> DB via podman-compose.dev.yml

## Quick commands

All backend tests: podman compose -f docker-compose.dev.yml exec backend pytest -v

Coverage: pytest --cov=app --cov-report=html

Frontend tests: podman compose -f docker-compose.dev.yml exec frontend npm run test:run

E2E tests: podman compose -f docker-compose.dev.yml exec frontend npm run test:e2e

# Repo Etiquette

Branches: feature/, bugfix/, hotfix/, backend/, frontend/, infra/, docs/*

Commits: type: description (feat|fix|test|docs|refactor|perf|chore|ci|backend|frontend|db)

Atomic commits; don't mix refactor + feature; rebase on main before merge; squash where appropriate

# Dev Setup

## Prerequisites

OS: Win 11 (WSL2) / macOS / Linux; Podman Compose v2; VSCode Remote-Containers; DB client (DBeaver/pgAdmin)

## First-time Steps

1. Clone: git clone <repo> && cd PomocAI
2. Env: cp backend/.env.example backend/.env; cp frontend/.env.example frontend/.env
3. Start: podman compose -f docker-compose.dev.yml up -d; logs -f
4. Verify: compose ps; pg_isready; curl http://localhost:8000/api/health; http://localhost:3000
5. API Docs: http://localhost:8000/api/docs (Swagger UI)

## DevContainers

Backend: .devcontainer/backend/devcontainer.json
Frontend: .devcontainer/frontend/devcontainer.json
Full-stack: .devcontainer/devcontainer.json

# Troubleshooting

## Backend

Port 8000 in use -> free port (lsof/netstat), or restart container
DB refused -> check postgres logs, DATABASE_URL format, port 5432 mapping
Alembic errors -> verify DATABASE_URL, alembic current/downgrade -1
CORS -> align CORS_ORIGINS with frontend URL; check FastAPI middleware in main.py
Import errors -> check PYTHONPATH includes /app; verify all __init__.py files exist

## Frontend

HMR in podman -> set server.hmr.host and expose port in compose
TS module types -> run vue-tsc; fix tsconfig paths; restart TS server
Proxy 404 -> verify vite.config.ts proxy to backend; ensure backend up
API base URL -> use VITE_API_BASE_URL env var; default http://localhost:8000/api

## Podman/Network

Frontend -> Backend name resolution -> use http://backend:8000 inside compose network
Port conflicts 3000/8000 -> free port or remap (e.g., 3001:3000, 8001:8000)

# Pre-push Checklist

- Lint/format ok; TS types ok; tests ok
- No secrets in code; commit format respected; atomic commits
- Rebased on main; no conflicts
- FastAPI async properly used; Pydantic schemas validated
