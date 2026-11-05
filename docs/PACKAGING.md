# Empacotamento do Ventude

O app roda em desenvolvimento com:

```powershell
cd $env:USERPROFILE\Downloads\Ventude
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
uv sync
uv run ventude
```

## Build one-folder (PyInstaller)

PyInstaller fica só no ambiente do projeto (dependency-group `dev`):

```powershell
uv sync --group dev
uv run pyinstaller --noconfirm packaging\ventude.spec
```

### Resultado (versão 0.4.0)

| Item | Valor |
|------|--------|
| Executável | `dist\Ventude\Ventude.exe` |
| Tamanho do .exe | ~8,6 MB |
| Pasta `dist\Ventude` | ~146 MB (one-folder com PySide6 + WinRT) |
| Forma | COLLECT (pasta `_internal` + exe) |

Para usar: abra `dist\Ventude\Ventude.exe` (não mova só o .exe; a pasta `_internal` precisa ir junto).

Credenciais e dados continuam em `%APPDATA%\Ventude\` (não ficam dentro do pacote).

### Observações

- O Windows pode mostrar aviso do **SmartScreen** ("Windows protegeu o PC"), porque o .exe **não é assinado**. Em "Mais informações" → "Executar assim mesmo".
- Antivírus às vezes demora na 1ª abertura de pastas grandes do PyInstaller.
- O pacote inclui o WinRT para mídia e os módulos Qt usados pela interface, inclusive QtSvg para os ícones.
- O Sign in with ChatGPT usa o navegador do sistema.
- Codex CLI **não** entra no pacote; se quiser esse provedor, instale aparte.
- Warnings do build sobre `fbclient.dll` / `OCI.dll` / `LIBPQ.dll` (plugins SQL opcionais do Qt) são esperados e podem ser ignorados: o Ventude usa SQLite via stdlib.

### Rebuild

```powershell
uv run pyinstaller --noconfirm packaging\ventude.spec
```

Log da análise: `build\ventude\warn-ventude.txt`.
