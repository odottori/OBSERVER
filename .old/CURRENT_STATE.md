# CURRENT_STATE — Stato sessione (Guardian)

## Stato corrente

- **Guardian spec attiva:** ARCHITECTURAL GUARDIAN **v1.9.4**.
- **Lingua:** ITALIANO.
- **SCOPE (hard):** READ consentito su tutta la repo (read-only); WRITE consentito **solo** in `./.doc/` salvo comando esplicito.
- **Comandi disponibili:** `guardian next` | `guardian sync` | `guardian allinea` | `guardian docfix` | `guardian programma`

### Semantica comandi (sintesi)
- **`guardian next`**: genera/aggiorna il `p0` just-in-time a partire da `TODO.md` (senza full-scan).
- **`guardian sync`**: sync incrementale docs↔repo basato su diff; applica *no-op policy*.
- **`guardian allinea`**: validazione forzata *codice/root ↔ canonici `.doc/`* (DocLint). Può AUTO-ADD solo finding S1.
- **`guardian docfix`**: manutenzione interna `.doc/` (docs-only).
- **`guardian programma`**: rigenerazione lenta (full-scan) del programma implementativo e dei canonici connessi; in chiusura esegue `guardian next`.

---

## Punti di controllo (Git)

Questi campi sono autoritativi solo quando calcolati nel repo Git (non in export ZIP senza `.git`).
- **Last aligned CODE_HEAD (sync no-op):** <git hash>
- **Last planned APP_HEAD (programma, esclude root `*.md`):** <git hash>
- **Last docfix DOC_HEAD (opzionale):** <git hash>

---

## Next-Resume Prompt

### p0 — WI-001: N2/v0.2.2 — GDELT Events: disambiguazione timestamp (AS-OF vs event_date)

Parallelizzabile: **NO** (modifica Root/Code)
Conflitti con (prompt NON eseguiti): nessuno (singolo work item)
Allowlist (scrittura):
- `scripts/news_alpha.py`
- `./.doc/READ.md`
- `./.doc/TECH.md`
- `./.doc/PROJ.md`
- `./.doc/DDIC.md`
- `./.doc/TODO.md`
- `./.doc/CURRENT_STATE.md`
- `./.doc/LOGBOOK.md`
- `./.doc/CHLG.md`
- `./.doc/WPLN.md`
Blocklist (NON toccare):
- Qualsiasi altro file

Azione:
- Modificare `scripts/news_alpha.py` (fixtures Events) per aggiungere `asof_date` e `gdelt.event_date` senza rompere consumer esistenti.
- Documentare il contratto timestamp (DR-6, READ/TECH/DDIC) e la regola AS-OF.

DoD:
- Fixtures Events includono `asof_date` e `gdelt.event_date`.
- Docs coerenti “Implemented vs Planned”.
- Test base: `python -m compileall .` PASS; `python main_test.py` PASS.
