# Deploy local (macOS) — painel TrendFit sempre no ar

Dois agentes do `launchd` mantêm o painel local rodando:

| Agente | O que faz | Quando |
|---|---|---|
| `com.trendfit.dashboard` | regenera `reports/dashboard.html` (coleta preço + roda o sistema) | 9h e 21h |
| `com.trendfit.serve` | servidor HTTP local que serve o painel | sempre (KeepAlive) |

## Acesso

```
http://localhost:5050/dashboard     # o painel
http://localhost:5050/refresh       # força regenerar agora
http://localhost:5050/health        # 'ok'
```

> Porta 5050 (a 5000 é usada pelo AirPlay Receiver do macOS). Mude via `TRENDFIT_PORT` no plist.

## Instalar / reinstalar

```bash
cp deploy/com.trendfit.*.plist ~/Library/LaunchAgents/
UID=$(id -u)
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.trendfit.serve.plist
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.trendfit.dashboard.plist
```

## Gerenciar

```bash
launchctl list | grep trendfit                                   # status
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.trendfit.serve.plist   # parar o servidor
tail -f /tmp/trendfit_serve.log                                  # log do servidor
```

Observações:
- Os plists usam caminhos absolutos desta máquina (`/Users/brunoliberatogirardi/Downloads/Dev/Trendfit`). Ajuste se mudar o local.
- O painel só roda com o Mac ligado/acordado (deploy local). Para acesso externo (celular), hospedar em VPS.
- `db/` e `reports/` são gitignored (regeneráveis).
