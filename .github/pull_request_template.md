## Summary



## Type of change



- [ ] Bug fix
- [ ] New feature
- [ ] Documentation only
- [ ] Refactor / tooling / CI
- [ ] Dependency updates

## Related issues



## Test plan



- [ ] `cd frontend && npm run lint`
- [ ] `cd frontend && npm run build`
- [ ] `cd backend && PYTHONPATH=. .venv/bin/python tests/test_discovery.py`
- [ ] `cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/ -q` (if pytest installed)
- [ ] Manual check: backend `GET /health` + frontend dashboard (describe briefly)

## Notes for reviewers



## Checklist

- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).
- [ ] No secrets, `.env`, `.env.local`, API keys, or `watchtower.db` are included in this PR.
- [ ] **[README.md](../README.md)** / **`backend/.env.example`** updated if APIs, user-facing behavior, or env vars changed.
- [ ] **`frontend/src/lib/types.ts`** and **`backend/app/models.py`** stay aligned if API shapes changed.
