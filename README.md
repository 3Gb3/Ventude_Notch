# Ventude

Dynamic Island, launcher e central de informações para Windows 10/11 (Python 3.12 + PySide6, gerenciado com uv).

## Rodar

```powershell
uv sync
uv run ventude
```

A ilha principal mostra a hora e a faixa em reprodução. Passe o mouse para ver o clima, os controles de música e a semana com o próximo compromisso. No primeiro uso, escolha sua cidade no ícone de clima. Os dados musicais vêm do player ativo do Windows.

A ilha **Ventude IA** abre ao passar o mouse ou pelo ícone de brilhos no painel principal. Use **+** para iniciar uma sessão e o seletor para retomar outra. Em **Sobre você**, edite, apague ou desative seu perfil. Quando a memória está ativa, as preferências entram no contexto enviado ao provedor de IA. Salvar uma sugestão de memória durante o chat pede confirmação.

Arraste o cabeçalho de cada ilha para posicioná-la, inclusive em outro monitor. As posições ficam salvas. Na engrenagem, **Restaurar posições** reúne as duas no monitor selecionado e **Sair do Ventude** encerra o aplicativo.

## Testes e lint

```powershell
uv run ruff check
uv run pytest
```

## Dados

Configurações e itens fixados ficam em `%APPDATA%\Ventude\ventude.db` (SQLite). Log em `%APPDATA%\Ventude\ventude.log`.

## Estrutura

```
src/ventude/
  app.py            inicialização (QApplication, bandeja, ilha)
  core/             config, events, logging, paths
  storage/          SQLite (configurações e itens fixados)
  services/         launcher (abrir/validar caminhos), monitores
  ui/               notch (ilha), themes, tray, pages/
  assistant/        IA (Fase 4, em desenvolvimento)
tests/
docs/               PROGRESS.md, ROADMAP.md
```

## Widgets (abas)

- **Clima**: Open-Meteo, sem chave. Busque a cidade uma vez; fica salva.
- **Calendário** / **Listas**: só neste PC (calendar.db, lists.db).
- **Notícias**: RSS G1, BBC Brasil, Tecnoblog.
- **Mercado**: Yahoo Finance (ações) + CoinGecko (cripto), sem chave.

## Empacotar

Veja `docs/PACKAGING.md`. O build com PyInstaller é opcional e não vem instalado.
