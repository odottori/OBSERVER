# .doc/ — Control Room Operativa (GUARDIAN)

Questa cartella contiene:
- **stato operativo umano** (editabile): `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`
- **libreria operativa derivata** (NON editare a mano): `.doc/canonical/derived/*`
- **manualistica GUARDIAN**: `.doc/_GUARDIAN/*`

Regola fondamentale:
- I canonici di progetto si editano **solo** in `./docs/`.
- Tutto ciò che è in `.doc/canonical/**` è generato/rigenerabile.

Comandi tipici:
- `py scripts/guardian.py sync`   (valida `docs/` e aggiorna indice/fingerprint)
- `py scripts/guardian.py lint`   (controlli struttura/coerenza)
- `py scripts/guardian.py derive` (genera `PROJ.md`, `TECH.md`, `DDT.md`)
- `py scripts/guardian.py next`   (genera prompt JIT dal TODO)
