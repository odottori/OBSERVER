# TODO — Work Items (GUARDIAN)

## Regole di parsing (guardian_next.py)
- Ogni Work Item DEVE iniziare con una riga che comincia con `WI-` (senza bullet).
- Il Work Item è considerato “selezionabile” solo se contiene `Status: OPEN`.
- Il comando `guardian next` prende SOLO il primo WI nel file; se non è OPEN, termina senza selezionare altro.

---

## Work Items (OPEN in cima)

WI-0001 — Titolo operativo
Status: OPEN

Allowlist:
- .doc/TODO.md
- .doc/CURRENT_STATE.md

DoD:
- Condizione verificabile
