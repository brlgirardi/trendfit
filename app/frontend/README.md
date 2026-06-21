# TrendFit Cockpit — Frontend

Cockpit React do TrendFit, dark theme estilo Glassnode Vector.

## Stack

- Vite + React 18 + TypeScript (strict)
- Tailwind CSS (dark mode via class)
- lightweight-charts v4 (candlesticks, séries de linha)
- Lucide React (ícones)

## Rodar

```bash
npm install
npm run dev      # http://localhost:3000  (proxy /api -> localhost:8502)
```

O backend (séries OHLCV, sinais, postura, macro) deve responder em
`http://localhost:8502` expondo:

- `GET /api/assets` -> `string[]`
- `GET /api/asset/:asset` -> `AssetData`
- `GET /api/macro` -> `MacroData`

Os contratos estão em `src/api/types.ts`.

## Build

```bash
npm run build    # tsc + vite build
npm run preview
```

## Estrutura

```
src/
  api/        client.ts, types.ts
  hooks/      useAssetData.ts, useMacroData.ts
  components/
    PostureBadge.tsx
    LeverageBadge.tsx
    Chart/    MainChart.tsx, MacroPanel.tsx
    Controls/ AssetSelector.tsx, SystemSelector.tsx
  styles/     globals.css
  App.tsx
  main.tsx
```

## Design system

| Token | Hex |
|---|---|
| bg-primary | `#0D0D0D` |
| bg-panel | `#1A1A1A` |
| border | `#2A2A2A` |
| bull | `#00FF88` |
| bear | `#FF3B3B` |
| neutral | `#FFB800` |
| very-bad | `#FF0000` |
| text-1 | `#E8E8E8` |
| text-2 | `#888888` |

Postura -> cor: ACUMULAR `#16a34a`, NEUTRO `#3b82f6`, CAUTELOSO `#f59e0b`,
DEFENSIVO `#ef4444`.
