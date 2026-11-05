# Progresso

Atualizado em 04/11/2026 (America/Sao_Paulo).

## Fase 0: concluída
- Projeto uv (`uv init --app --package`), Python 3.12, PySide6/httpx; ruff e pytest.
- `uv run ventude` como entry point. Versão atual: 0.2.0.

## Fase 1: concluída
- Ilha frameless, translúcida, always-on-top, fora do Alt+Tab (Qt.Tool), tema preto/grafite/verde.
- Expansão animada, atraso configurável, bandeja com Monitor/Sair, settings em SQLite, DPI PassThrough.

## Fase 2: concluída
- Apps e pastas fixados (abrir, reordenar, remover, validar, persistir).

## Fase 3: concluída
- Mídia WinRT com eventos (sem polling), card no Início, faixa no modo compacto.

## Fase 4: concluída (login real ainda depende do usuário)
- SIWC documentado, Responses API, Codex app-server, ferramentas, permissões, DPAPI, aba IA.

## Fase 5: concluída
- Cache SQLite com TTL (`cache.db`).
- Clima: Open-Meteo + geocoding (sem chave); cidade salva em settings.
- Calendário: eventos locais em `calendar.db` (mês, adicionar/remover).
- Notícias: RSS G1, BBC Brasil, Tecnoblog (sem chave), cache 15 min.
- Mercado: Yahoo Finance chart (ações/índice) + CoinGecko (BTC/ETH); cache 10 min. Stooq foi tentado e responde 404 neste ambiente; trocado por Yahoo.
- Listas: aba nova com listas/itens locais em `lists.db`.
- Abas Clima/Calendário/Notícias/Mercado/Listas deixam de ser placeholder.

## Fase 6: concluída (empacotamento preparado, build PyInstaller não executado)
- Revisão de arquitetura em `docs/ARCHITECTURE.md`.
- Multi-monitor: reposiciona em screenAdded/Removed e geometryChanged; índice inválido volta ao monitor 0.
- Script `scripts/smoke.ps1`, `docs/PACKAGING.md`, `packaging/ventude.spec`.
- Versão 0.2.0; organização Qt "Ventude".
- Testes ampliados (54 passed). PyInstaller fica como passo opcional do usuário (`uv add --dev pyinstaller`).

## Testes (última rodada)
- `uv run ruff check`: All checks passed!
- `uv run pytest -q`: 54 passed.
- Smoke `uv run ventude` ~9 s: processo vivo, depois encerrado; 0 restantes.
- Rede real verificada: Open-Meteo (Cachoeirinha), RSS G1, Yahoo (Ibovespa/PETR4/…) e CoinGecko.

## Pendências gerais
- Login ChatGPT real e Codex CLI (usuário).
- Build PyInstaller completo (usuário; precisa `uv add --dev pyinstaller`).
- Ferramentas no provedor plano ChatGPT (namespaces não documentados).
- Chaves opcionais extras (não necessárias hoje).

## Build .exe (04/11/2026 ~23:30 America/Sao_Paulo)
- `uv add --dev pyinstaller` (só no venv do projeto).
- `uv run pyinstaller --noconfirm packaging\ventude.spec` — sucesso (EXIT 0).
- Spec reforçado com collect_all/hiddenimports (PySide6, winrt, jsonschema, jwt, cryptography, httpx…).
- Smoke: `dist\Ventude\Ventude.exe` vivo após 9 s; log `Ventude iniciado`; widgets buscaram RSS/Yahoo/CoinGecko; processo encerrado, 0 restantes.
- Artefato: `dist\Ventude\Ventude.exe` (~8,2 MB); pasta dist ~700 MB / 4501 arquivos.