# Security practices (Yuno Agent Platform)

## Secrets

- **Never commit** `.env` — listed in `.gitignore`
- API keys (`XAI_API_KEY`, `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`) stay in environment variables only
- If a Telegram or LLM key is exposed in chat/email, **revoke immediately** via provider console and rotate

## Assessment PDF expectations

The challenge requires a working platform with real runtime, persistence, and external channel. Security-related items:

| Topic | Implementation |
|--------|----------------|
| API keys | Env vars + `.env.example` template (no real keys) |
| PII / GDPR | Jarvis reference code had DSAR flows; this MVP focuses on agent orchestration — extend before production |
| Guardrails | `blocked_topics` enforced in `app/services/guardrails.py` on input and output |
| Telegram | Token only in env; bot uses polling (no public webhook secret in repo) |

## Production checklist (before deploy)

- [ ] Rotate all keys after development
- [ ] Use HTTPS reverse proxy (nginx/Caddy) in front of API and UI
- [ ] Restrict CORS to your frontend origin only
- [ ] Run PostgreSQL with strong password (not default `yuno/yuno`)
- [ ] Do not expose Postgres/Redis ports publicly on VPS
- [ ] Enable rate limiting on public API (e.g. middleware or API gateway)
