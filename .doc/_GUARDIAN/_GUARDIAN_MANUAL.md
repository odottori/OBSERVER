# ARCHITECTURAL GUARDIAN — MANUALE OPERATIVO (v2.3)

## Scopo
GUARDIAN mantiene la coerenza tra **repo reale** (codice/config) e la libreria dei canonici operativi in `./.doc/`.

Obiettivo operativo:
- avere un backlog di lavoro **stabile** (`.doc/TODO.md`)
- avere un prompt operativo **immediato** e con scope circoscritto (`p0` in `.doc/CURRENT_STATE.md`)
- avere una libreria di canonici **anti-drift** (indice + fingerprint in `.doc/CANONICAL_LIBRARY.md`)

## Layout canonici (2.0+)
- Canonici di progetto (input, read-only): `./docs/`
- Canonici operativi (output):
  - `.doc/canonical/project/` = copie 1:1 dei canonici progetto (generate da `sync`)
  - `.doc/canonical/derived/` = canonici compatti (PROJ/TECH/DDT) per uso operativo (generati da `derive`)
- Indice/Fingerprint: `.doc/CANONICAL_LIBRARY.md`

Legacy (progetti precedenti):
- Se trovi `.doc/canon/` e/o `.doc/CANON_LIBRARY.md`, usa `guardian migrate` per riallineare ai nomi nuovi (consigliato).

## Control Plane (file in root `.doc/`)
- `.doc/TODO.md` = backlog (Work Items OPEN)
- `.doc/CURRENT_STATE.md` = checkpoint + `p0` (prompt operativo immediato)
- `.doc/LOGBOOK.md` = evidenze, decisioni, delta-candidates

## CLI consigliata
Comando portabile (Windows incluso):

```powershell
py scripts\guardian.py
```

Il wrapper `guardian.py` mostra un help sintetico se invocato senza argomenti.

### Mapping comandi
| Comando | Effetto | Implementazione |
|---|---|---|
| `guardian init` | crea template `.doc/` | `guardian_ops.py init` |
| `guardian migrate` | migra `.doc/canon/` -> `.doc/canonical/` (e indice) | `guardian_ops.py migrate` |
| `guardian sync` | aggiorna `.doc/canonical/project/` e `CANONICAL_LIBRARY.md` | `guardian_ops.py sync` |
| `guardian derive` | genera `.doc/canonical/derived/PROJ.md`, `TECH.md`, `DDT.md` | `guardian_ops.py derive` |
| `guardian lint` | verifica coerenza docs -> .doc e drift | `guardian_ops.py lint` |
| `guardian status` | riepilogo rapido | `guardian_ops.py status` |
| `guardian programme` | recovery backlog (baseline) | `guardian_ops.py programme` |
| `guardian next` | genera `p0` da primo WI OPEN | `guardian_next.py next` |

Sinonimi legacy supportati dal wrapper:
- `guardian allinea` -> `guardian lint`
- `guardian programma` -> `guardian programme`

## Semantica operativa (essenziale)

### `sync` (incrementale, DOCSET -> .doc)
Allinea `.doc/canonical/project/` ai canonici progetto elencati in `DOCSET_MANIFEST.json`.
- Non modifica `docs/`.
- Aggiorna `CANONICAL_LIBRARY.md` e checkpoint fingerprint.

### `derive` (canonici compatti)
Genera una libreria operativa compatta, pensata per IDE e prompt JIT:
- `.doc/canonical/derived/PROJ.md` (retail-friendly: scopo, use-cases, comandi rapidi)
- `.doc/canonical/derived/TECH.md` (architettura, runner, failure modes)
- `.doc/canonical/derived/DDT.md` (data dictionary compatto)

### `next` (JIT)
Genera/aggiorna `p0` in `.doc/CURRENT_STATE.md` dal primo Work Item OPEN in `.doc/TODO.md`.

## Regola anti-churn (hard)
Se l'esito è `OK`/`PASS` o `no-op`, evitare scritture inutili su `CURRENT_STATE.md` e `LOGBOOK.md`.

## Installazione in Windsurf
Copia 1:1:
- `.doc/_GUARDIAN/_GUARDIAN_rule.md` -> `.windsurf/rules/guardian-rule.md`
- `.doc/_GUARDIAN/_GUARDIAN_workflow.md` -> `.windsurf/workflows/guardian-workflow.md`
