# Arquitetura do Ventude

```
src/ventude/
  app.py                 bootstrap Qt, serviços, bandeja, ilha
  core/                  config, events, logging, paths, async_worker
  storage/               SQLite (settings + pinned)
  services/              launcher, monitors, media, cache, weather, news, market,
                         calendar_store, lists_store
  assistant/             agente, auth SIWC, providers, tools, permissions, history
  ui/                    notch, tray, themes, pages/*
```

## Threads

- **UI (Qt):** ilha, páginas, bandeja.
- **ventude-media:** loop asyncio WinRT.
- **ventude-async:** loop asyncio para HTTP, OAuth e Codex.

Sinais Qt (`QueuedConnection` padrão entre threads) levam resultados à UI.

## Dados em `%APPDATA%\Ventude`

| Arquivo | Conteúdo |
|---------|----------|
| ventude.db | settings e pinned |
| assistant.db | chat + audit_log |
| credentials.bin | tokens/chave (DPAPI) |
| cache.db | cache dos widgets |
| calendar.db | eventos locais |
| lists.db | listas |
| ventude.log | log rotativo |
