---
docset_version: 1.2.5
last_updated: 2026-01-27
status: support
---

# 011 — Matrice Gap Derivati (root → downstream) — v1.2.5

## Scopo
Rendere espliciti i **gap derivati**: un *root gap* (mancanza primaria) genera blocchi ed effetti a cascata su moduli, UI e scenari.

Riferimenti:
- `docs/009_GAP_REGISTER.md` (gap con acceptance criteria)
- `docs/010_MODULE_REGISTRY.md` (moduli e maturità)

## Come leggere
- **Root gap**: la mancanza primaria (es. `GAP-OMS`)
- **Blocca**: moduli o capacità direttamente bloccate
- **Gap derivati**: capacità indirettamente impossibili/fragili
- **Scenari**: quali scenari operativi (1–5) ne risentono

## Root gap ed effetti downstream

| Root gap | Blocca (diretto) | Gap derivati (downstream) | Scenari impattati |
|---|---|---|---|
| `GAP-OMS` | MOD-OMS, workflow ordini | `GAP-ALERTING`, UI trade ticket, reconciliation, attribution affidabile | Tutti live |
| `GAP-BROKER-ADAPTER` | MOD-BROKER-ADAPTER, LIVE-GRADE | kill-switch reale, fills reali, esposizione real-time | Tutti live |
| `GAP-EXEC-LOG` | monitoring/analytics | TCA, slippage calibration, attribution, drift baselines | Tutti paper/live |
| `GAP-RISK-HARDEN` | risk controls | stop dinamici, concentration limits, kill-switch policy | 1–5 |
| `GAP-GUARDRAILS` | disciplina operativa retail | cooling-off, discipline-mode, hard blocks | 1–5 |
| `GAP-CA-COLLECTOR` | event strategies | timing split/dividendi, false signals | 3 |
| `GAP-MACRO-LAYER` | sector rotation | regime detection, macro filters | 4 |
| `GAP-PAIRS-ENGINE` | pairs trading | z-score monitoring, neutrality enforcement | 5 |
