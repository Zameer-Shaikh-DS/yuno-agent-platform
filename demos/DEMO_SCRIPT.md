# End-to-end demo checklist

Record a 5–8 minute video covering:

- [ ] `docker compose up --build` — postgres, redis, api, web all healthy
- [ ] Open http://localhost:3000
- [ ] **Agents** page: show 5 seeded agents (Researcher, Writer, SupportTriage, SupportResponder, TelegramGateway)
- [ ] Edit an agent: change tools, guardrails, save
- [ ] **Workflows**: open "Research → Writer" template
- [ ] Enter input: "What are multi-agent orchestration patterns?"
- [ ] Click **Run Workflow** — show output
- [ ] **Monitor**: select run — events, inter-agent messages, token/cost table
- [ ] Live feed shows WebSocket events during run
- [ ] **Telegram**: `/start`, send a question, show bot reply
- [ ] Optional: `/run research Your topic here`
- [ ] README architecture section (brief scroll)

## Environment for demo

```env
XAI_API_KEY=xai-...
XAI_MODEL=grok-4.1-fast
TELEGRAM_BOT_TOKEN=...
MOCK_LLM=0
```

Use real Grok for the recorded demo (not MOCK_LLM).
