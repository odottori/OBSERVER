# LOGBOOK — Registro azioni (Guardian)

## 2026-01-20

### Guardian docfix — Post-rename `_GUARDIAN_*` (nota manuale)
- Fix: aggiornata in `./.doc/_GUARDIAN/_GUARDIAN_MANUAL.md` la nota sul naming dei file Guardian (`_GUARDIAN_*.md`).

### Guardian docfix — Coerenza versione spec + mapping Windsurf
- Fix: allineata la versione della spec in `CURRENT_STATE.md` a v1.9.4 (coerente con `GUARDIAN_*`).
- Fix: corretto il mapping nel manuale per la rule Windsurf: `./.doc/_GUARDIAN/_GUARDIAN_rule.md` → `.windsurf/rules/guardian-rule.md`.

### Guardian allinea — DocLint (state sync HEAD/CODE_HEAD)
- Evidenza: `HEAD=CODE_HEAD=c393eac87f9b234649beca30f018831c7c782621`.
- Esito DocLint: **FAIL** (drift canonici) — `CURRENT_STATE.md` riportava checkpoint `Last aligned HEAD/CODE_HEAD` non aggiornati.
- Azione (docs-only): aggiornati i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` in `CURRENT_STATE.md` al commit corrente.

### Guardian docfix — Spec v1.8.0 + Git versioning (APP_HEAD) + state fields
- Evidenza: definita la spec Guardian v1.8.0 (riduzione letture/scritture e definizioni Git: CODE_DIRTY/DOC_DIRTY/CODE_HEAD/APP_HEAD/DOC_HEAD).
- Fix: corretta la pathspec per `APP_HEAD` (esclusione dei soli `*.md` in root) in `GUARDIAN_rule.md` e `GUARDIAN_workflow.md`.
- Azione (docs-only): aggiornato `CURRENT_STATE.md` a v1.8.0 e aggiunto `Last planned APP_HEAD`.

## Delta-candidates (pending planning)

### DC-2026-01-20-001 [S2] Coerenza header TODO: “OPEN ONLY” vs policy “solo DA FARE (OPEN)”
- WHY: `TODO.md` ha titolo `Programma implementativo (OPEN ONLY)` e include sezioni “Implemented”/checklist; la policy corrente del Guardian richiede che `TODO.md` contenga **solo lavoro DA FARE (OPEN)** e che lo storico/evidenze vivano in `LOGBOOK.md`.
- Evidenza (DocLint): `./.doc/TODO.md` (header e sezioni post-backlog) vs `./.doc/CURRENT_STATE.md` (Policy TODO) e `./.doc/GUARDIAN_rule.md`.
- Allowlist (write): `./.doc/TODO.md`
- Blocklist: Qualsiasi altro file
- Azione suggerita: eseguire `guardian programma` per normalizzare `TODO.md` secondo la policy (senza perdita di informazione: spostare eventuali elementi “DONE/Implemented” in `LOGBOOK.md` o altra struttura canonica).

## 2026-01-19

### Governance — Introdotto `guardian programma` + RECOVERY MODE (v1.7)
- Decisione: la rigenerazione del programma (TODO/CURRENT_STATE) e' lenta e non deve essere un side-effect di `guardian allinea`/`guardian sync`.
- Nuova semantica: `guardian allinea` = DocLint PASS/FAIL + patch canonici impattati; `guardian programma` = normalizzazione del programma implementativo (**solo DA FARE**) + riallineamento `CURRENT_STATE.md`.
- Auto-run consentito solo in caso di **errore strutturale** (recovery), con output trasparente e progress `[1/5]..[5/5]`.
- File `.doc/` toccati: `GUARDIAN_manual.md`, `GUARDIAN_rule.md`, `GUARDIAN_workflow.md`, `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Docfix — Semantica `guardian programma` (lettura root, esclusi `*.md`)
 - Decisione: `guardian programma` ricostruisce l’evidenza con **rilettura deterministica dell’applicazione (read-only)**:
   - include file tracciati NON in `./.doc/` (esclusi binari; contenuti testuali letti)
   - esclude `*.md` nella root (path senza directory)
   - include `*.md` in `./.doc/`
   - per file molto grandi o non testuali: solo metadati (path + size)
 - Azione: aggiornati i canonici `GUARDIAN_manual.md`, `GUARDIAN_rule.md`, `GUARDIAN_workflow.md` per esplicitare la regola.
 - Note: gli omologhi `.windsurf/*` vanno mantenuti allineati 1:1 (stessa riga aggiunta nelle sezioni `guardian programma`).
 - File `.doc/` toccati: `GUARDIAN_manual.md`, `GUARDIAN_rule.md`, `GUARDIAN_workflow.md`, `LOGBOOK.md`.

### Guardian programma — Verifica p0 (NO-OP backlog) + state sync
 - Evidenza: `HEAD=189292b1bac439c1c18da0ce835c3281e8c07353` (docs-only) e `CODE_HEAD=53333a7c418f28199ab905ed51cd80cc959d2381`.
 - Verifica (p0): in `scripts/news_alpha.py` non risulta implementato alcun command group `history` ⇒ `p0` resta valido (NOT_DONE) e non viene promosso.
 - Nota: con v1.7.4 la rigenerazione del programma usa rilettura deterministica dell’applicazione (read-only) con esclusioni; questa voce resta valida sul merito (p0 NOT_DONE).
 - Azione (docs-only): riallineati i punti di controllo `Last aligned HEAD/CODE_HEAD` in `CURRENT_STATE.md`.
 - File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Esecuzione p0 (cfg-5) — Dependabot + SECURITY
- Evidenza: creati `/.github/dependabot.yml` e `/SECURITY.md`.
- Evidenza: commit+push completati su `origin/main` con `HEAD=CODE_HEAD=e7178661a5c1615c7639399e44d016e543d11392` (commit `chore: add dependabot + security policy`).
- File root toccati (allowlist p0): `.github/dependabot.yml`, `SECURITY.md`.
- Note: chiusura `cfg-5` tracciata qui; `TODO.md` resta programma implementativo (**solo DA FARE** + `Prompt Backlog (Guardian)`), mentre le evidenze di esecuzione vivono in `LOGBOOK.md`.

### Guardian programma — Rigenerazione backlog (p0 promosso a N2/v0.2)
- Evidenza: `HEAD=7b9ad70afa4c20404948eb116fffc7056d226d9c` (docs-only) e `CODE_HEAD=e7178661a5c1615c7639399e44d016e543d11392`.
- Azione (docs-only): rimosso il p0 transitorio di chiusura `cfg-5` e promosso `p0` al primo lavoro non implementato già tracciato in `TODO.md` (NEWS-ALPHA v0.2: history lane GDELT + CLI `history`).
- File `.doc/` toccati: `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Guardian docfix — Coerenza canonici (HEAD/CODE_HEAD + naming file)
- Evidenza: drift tra `HEAD` e `CODE_HEAD` e riferimenti legacy/misnamed al manuale (`GUARDIAN_MANUAL.md` non presente nel tree; canonical = `GUARDIAN_manual.md`).
- Azione (docs-only): riallineati i campi `Last aligned HEAD`/`Last aligned CODE_HEAD` in `CURRENT_STATE.md` e normalizzati i riferimenti al manuale in `LOGBOOK.md`.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Docs-only — Formalizzata regola avanzamento catena prompt (p0/p+1..p+3)
- Azione: aggiornata `guardian-rule.md` per rendere vincolante l’aggiornamento del `Prompt Backlog (Guardian)` in `TODO.md` e del `Next-Resume Prompt` in `CURRENT_STATE.md` quando un allineamento è **non no-op** e chiude `p0`.
- File `.doc/` toccati: `guardian-rule.md`, `LOGBOOK.md`, `CURRENT_STATE.md`.

### Guardian allinea — Canonici Guardian v1.5 (GUARDIAN_*) + promozione catena prompt
- Evidenza: introdotti i canonici `GUARDIAN_manual.md`, `GUARDIAN_rule.md`, `GUARDIAN_workflow.md` e aggiornate le regole Windsurf corrispondenti; rimossi i precedenti `guardian-rule.md`/`guardian-workflow.md`.
- Azione (docs-only): riallineato `TODO.md` promuovendo `p0` a `cfg-5` e marcando `cfg-3`/`cfg-4` come **CHIUSO**; riallineato `CURRENT_STATE.md` al nuovo `p0`.
- File `.doc/` toccati: `GUARDIAN_manual.md`, `GUARDIAN_rule.md`, `GUARDIAN_workflow.md`, `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — Guardian v1.5 canonicals + Windsurf sync
- Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=5ea66585b21a08a062a25c579d88d79eb180b9cb` (commit `chore: guardian v1.5 canonicals + windsurf sync`).
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — commit docs-only (state sync)
- Evidenza: push completato su `origin/main` con `HEAD=554b0fd0303af795af695e08996f61311190cf5c` e `CODE_HEAD=5ea66585b21a08a062a25c579d88d79eb180b9cb` (commit `docs: sync guardian state after push (HEAD/CODE_HEAD)`).
- Azione (docs-only): aggiornato `CURRENT_STATE.md` distinguendo `Last aligned HEAD` (HEAD) da `Last aligned CODE_HEAD` (ultimo commit non-`.doc/`).
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — Guardian v1.5.1 wording + state sync
- Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=82a921ae58f1ac97fcba3fe5b68f34dcc6449e12` (commit `chore: guardian v1.5.1 wording + state sync`).
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — guardian allinea (doclint) + windsurf sync
- Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=8b2852e5b0e55ec9ecf15d73aa450ba485fba276` (commit `chore: guardian allinea (doclint) + windsurf sync`).
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — .gitignore hardening
- Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=6daa34bbffcd1021211291ab7730a322268891ac` (commit `chore: harden gitignore`).
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Docs-only — Chiusura materiale temporaneo `.appoggio/NEWS_ALPHA_NEXT_CHAT_PROMPT.md`
- Verifica: i dettagli operativi precedentemente “solo prompt” risultano tracciati nei canonici `.doc/` (contratto CLI Wave 7H in `TODO.md` → Processo N2, v0.2; standard tooltips/glossario/progressive disclosure Wave 8 in `TODO.md`).
- Decisione: `.appoggio/NEWS_ALPHA_NEXT_CHAT_PROMPT.md` è **deprecato** e deve essere rimosso dopo assorbimento completo; non è più una fonte “viva”.
- File `.doc/` toccati: `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Docs-only — Prompt Backlog: `p0` marcato CHIUSO
- Azione: marcato `p0` come **CHIUSO** in `TODO.md` e riallineato il titolo del `p0` in `CURRENT_STATE.md`.
- File `.doc/` toccati: `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-commit (HEAD/CODE_HEAD) — aggiornamento `CURRENT_STATE.md`
- Evidenza: commit+push completati su `main` (`34c0edf4010006bcf924f1d38e7d4e3076393769`).
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — aggiornamento `CURRENT_STATE.md`
- Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=2df18915ba02a5625a5f54e35b4af8aa03e6f317`.
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Sync post-push (HEAD/CODE_HEAD) — `.gitignore` hardening
- Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=6daa34bbffcd1021211291ab7730a322268891ac` (commit `chore: harden gitignore`).
- Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
- File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.

### Guardian allinea — DEROGA NO-OP (solo docs): Prompt Backlog in TODO + p0 testuale
- Evidenza: `git status --porcelain` vuoto e `CODE_HEAD` invariato (`34c0edf4010006bcf924f1d38e7d4e3076393769`) ⇒ allineamento sarebbe no-op.
- Deroga: autorizzazione esplicita dell’utente per introdurre la sezione `## Prompt Backlog (Guardian)` in `TODO.md` e copiare `p0` testualmente in `CURRENT_STATE.md`.
 - Nota operativa: la rimozione fisica è **fuori allowlist** di questa patch docs-only; se il file è presente nel repo locale, rimuoverlo con `git rm` e committare in un change dedicato.
 - File `.doc/` toccati: `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.
 
 ### Docs-only — Prompt Backlog: `p0` marcato CHIUSO
 - Azione: marcato `p0` come **CHIUSO** in `TODO.md` e riallineato il titolo del `p0` in `CURRENT_STATE.md`.
 - File `.doc/` toccati: `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.
 
 ### Sync post-commit (HEAD/CODE_HEAD) — aggiornamento `CURRENT_STATE.md`
 - Evidenza: commit+push completati su `main` (`34c0edf4010006bcf924f1d38e7d4e3076393769`).
 - Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
 - File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.
 
 ### Sync post-push (HEAD/CODE_HEAD) — aggiornamento `CURRENT_STATE.md`
 - Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=2df18915ba02a5625a5f54e35b4af8aa03e6f317`.
 - Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
 - File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.
 
 ### Sync post-push (HEAD/CODE_HEAD) — `.gitignore` hardening
 - Evidenza: push completato su `origin/main` con `HEAD=CODE_HEAD=6daa34bbffcd1021211291ab7730a322268891ac` (commit `chore: harden gitignore`).
 - Azione (docs-only): aggiornati in `CURRENT_STATE.md` i campi `Last aligned HEAD` e `Last aligned CODE_HEAD` al nuovo valore.
 - File `.doc/` toccati: `CURRENT_STATE.md`, `LOGBOOK.md`.
 
 ### Guardian allinea — DEROGA NO-OP (solo docs): Prompt Backlog in TODO + p0 testuale
 - Evidenza: `git status --porcelain` vuoto e `CODE_HEAD` invariato (`34c0edf4010006bcf924f1d38e7d4e3076393769`) ⇒ allineamento sarebbe no-op.
 - Deroga: autorizzazione esplicita dell’utente per introdurre la sezione `## Prompt Backlog (Guardian)` in `TODO.md` e copiare `p0` testualmente in `CURRENT_STATE.md`.
- Azione Guardian (docs-only): introdotto backlog prompt canonico in `TODO.md` (p0/p+1..p+3 con allowlist/conflitti) e aggiornato `CURRENT_STATE.md` per riportare `p0` in forma testuale.
- File `.doc/` toccati: `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Consolidamento (commit+push) — update CI workflow + config Windsurf Guardian
- Evidenza: commit su `main` con messaggio `chore: update CI workflow and windsurf guardian config`.
- Evidenza: push su `origin/main` completato.
- Evidenza: `CODE_HEAD` aggiornato a `1de9076e5fff298cb1070894e718d3856d4e7b3c`.

### Guardian allinea — policy Next-Resume Prompt (testuale, no riassunti) — NON no-op
- Evidenza: necessaria correzione di protocollo emersa in chat (il Next-Resume Prompt va ripreso e riportato testualmente da `CURRENT_STATE.md`).
- Azione Guardian (docs-only): aggiornati i canonici Guardian in `.doc/` per rendere vincolante: no “riassunto sintetico” nei messaggi generici.
- File `.doc/` toccati: `GUARDIAN_manual.md`, `guardian-rule.md`, `guardian-workflow.md`, `LOGBOOK.md`.

### Consolidamento (commit+push) — cleanup `.old/` (rimozione archivio)
- Evidenza: commit su `main` con messaggio `chore: drop .old archive and update guardian state`.
- Evidenza: push su `origin/main` completato.
- Evidenza: `CODE_HEAD` aggiornato a `9ef6ca82e39dbb6b3d2032c2ae975458754f19f8`.

### Consolidamento (commit+push) — repo hygiene + Windsurf rules + `src/data` backfill
- Evidenza: commit su `main` con messaggio `chore: repo hygiene + windsurf rules + add src.data backfill`.
- Evidenza: push su `origin/main` completato.
- Evidenza: `CODE_HEAD` aggiornato a `af95b4eef7c9f846ac462ea9280858798b2234c8`.

### Consolidamento (commit+push) — update manuale Guardian (Windsurf rule locations)
- Evidenza: commit su `main` con messaggio `docs: clarify guardian windsurf rule locations`.
- Evidenza: push su `origin/main` completato.
- Evidenza: `HEAD` aggiornato a `36fdfea40933cbeff1ec9546c5b0f26e09a767de`.

### Consolidamento (commit+push) — CI GitHub Actions nei canonici
- Evidenza: commit su branch `main` con messaggio `docs: document minimal GitHub Actions CI guard`.
- Evidenza: push su `origin/main` completato.
- Evidenza: `CODE_HEAD` aggiornato a `5a3d518966ad1d9002683cb0e9daa911d516f591`.

### Guardian allinea — CI (GitHub Actions) replicata nei canonici `.doc/` — NON no-op
- Evidenza: `git status --porcelain` non vuoto (drift Root + `.doc/`).
- Evidenza: `CODE_HEAD` corrente (ultimo commit che modifica path fuori da `.doc/`) = `ce04ed08ae799fa19db376a91625d2e54fb9b9d3`.
- Azione Guardian (docs-only): allineati i canonici `.doc/` per includere il guard CI (install deps + compileall + `main_test.py`).
- File `.doc/` toccati: `READ.md`, `WPLN.md`, `CHLG.md`, `TECH.md`, `TODO.md`, `CURRENT_STATE.md`, `LOGBOOK.md`.

### Aggiornamento canonici Root: sezione CI (GitHub Actions) — NON no-op
- Evidenza: `git status --porcelain` segnala modifiche non committate su canonici Root.
- Evidenza: `CODE_HEAD` corrente (ultimo commit che modifica path fuori da `.doc/`) = `ce04ed08ae799fa19db376a91625d2e54fb9b9d3` (invariato) ⇒ working tree non pulito.
- Nota: `.github/workflows/ci.yml` risulta già presente nello snapshot; aggiornati solo i canonici per documentare il guard CI.
- Drift (Root): `README.md`, `WORKPLAN.md`, `CHANGELOG.md`, `TODOLIST.md`, `TECHNICAL_ARCHITECTURE.md`.

### Allineamento (pre-check no-op) — NON no-op
- Evidenza: `git status --porcelain` segnala modifiche non committate e nuovi file fuori da `.doc/`.
- Evidenza: `CODE_HEAD` corrente (ultimo commit che modifica path fuori da `.doc/`) = `40b9db0cfbe5a645ababeacb55809b836ce17681`.
- Azione Guardian (docs-only): aggiornato `CURRENT_STATE.md` per tracciare drift e impostare il prossimo passo su consolidamento (commit/revert) prima dell’allineamento dei canonici.

### Drift rilevato (summary)
- Root: `README.md`, `PROJECT_OVERVIEW.md`, `TECHNICAL_ARCHITECTURE.md`, `WORKPLAN.md`, `TODOLIST.md`, `CHANGELOG.md`.
- Code/Test: modifiche a `scripts/sentinel.py`, `scripts/ops_reset.py`, `scripts/setup.py`, vari `src/tools/*` e nuovo `src/tools/verify_provenance.py` + `test/test_verify_provenance.py`.

### Sync post-commit (working tree pulito)
- Evidenza: commit applicati per Root+codice (incl. `src/tools/verify_provenance.py` + test) e commit separato per `.doc/`.
- Evidenza: `git status --porcelain` vuoto.
- Evidenza: `CODE_HEAD` aggiornato a `1e8d3208b2d2178173f8755a848f6702bf1454eb`.
- Azione Guardian (docs-only): riallineato `CURRENT_STATE.md` per marcare drift consolidato e riposizionare il Next-Resume Prompt su `guardian allinea` post-commit.

### Drift rilevato (nuovo, post-sync) — NON no-op
- Evidenza: `git status --porcelain` segnala nuove modifiche non committate su Root + nuovi file.
- Drift: modifiche a `.gitattributes`, `README.md`, `WORKPLAN.md`, `TODOLIST.md`, `CHANGELOG.md` e nuovo file `.editorconfig`.
- Azione Guardian (docs-only): aggiornato `CURRENT_STATE.md` per tracciare il drift e impostare il prossimo passo su commit/revert prima di ulteriori allineamenti.

### Sync post-commit (repo hygiene)
- Evidenza: drift consolidato con commit (Root + `.editorconfig` + `.gitattributes`).
- Evidenza: `git status --porcelain` vuoto.
- Evidenza: `CODE_HEAD` aggiornato a `51bedd112b38855c9dc7584b969603c1652c44db`.
- Azione Guardian (docs-only): aggiornato `CURRENT_STATE.md` per riallineare `Last aligned CODE_HEAD` e riportare lo stato a working tree pulito.

### Drift rilevato (nuovo) — verify_provenance + CI metadata
- Evidenza: `git status --porcelain` segnala:
  - `M src/tools/verify_provenance.py`
  - `?? .github/`
- Nota: `CODE_HEAD` invariato (resta `51bedd112b38855c9dc7584b969603c1652c44db`) ma il working tree non è pulito ⇒ non è no-op.
- Azione Guardian (docs-only): aggiornato `CURRENT_STATE.md` per tracciare il drift e impostare il prossimo passo su commit prima dell’allineamento canonici.

### Sync post-commit (verify_provenance + GitHub workflows)
- Evidenza: drift consolidato con commit (aggiornamento `src/tools/verify_provenance.py` + nuovo path `.github/`).
- Evidenza: `git status --porcelain` vuoto.
- Evidenza: `CODE_HEAD` aggiornato a `59a6aa9e2f79b52ad26248501aa476125647bafc`.
- Azione Guardian (docs-only): aggiornato `CURRENT_STATE.md` per riallineare `Last aligned CODE_HEAD` e riportare lo stato a working tree pulito.

### Adozione standard Next-Resume Prompt auto-consistente
- Azione Guardian (docs-only): registrata l'adozione dello standard Next-Resume Prompt auto-consistente (parallelizzabilità + 3 next) come azione docs-only.

### Allineamento canonici (A1/B1/F) — stato reale + runbook
- Azione Guardian (docs-only): aggiornato `TODO.md` per riflettere: A1 wrapper rimossi, B1 standard `<PY>`, F2 provenance gate **partially implemented** con spunte (tool + wiring + denylist + test).
- Azione Guardian (docs-only): aggiornati `CURRENT_STATE.md`, `TECH.md`, `READ.md`, `CHLG.md` per coerenza: Root solo su comando esplicito; rimozione riferimenti legacy; nota gate provenance; acceptance con `<PY>`.

### Allineamento canonici (F2) — disclosure report (SAFE) completata
- Evidenza: `CODE_HEAD` corrente (ultimo commit che modifica path fuori da `.doc/`) = `ce04ed08ae799fa19db376a91625d2e54fb9b9d3`.
- Evidenza: diff fuori `.doc/` dal precedente `Last aligned CODE_HEAD` include `src/intelligence_engine.py` (disclosure contatori provenance nel report).
- Azione Guardian (docs-only): aggiornati `TODO.md`, `TECH.md`, `CURRENT_STATE.md` per marcare F2 disclosure report = implementata (resta pending solo hardening persistenza).

## 2026-01-17

### Bootstrap .doc/
- Creati/rigenerati i canonici in `.doc/` a partire dai file Root (read-only): `TODO.md`, `PROJ.md`, `CHLG.md`, `DDIC.md`, `TECH.md`, `READ.md`, `WPLN.md`.
- Creati i file utility: `LOGBOOK.md`, `CURRENT_STATE.md`.

Motivazione: inizializzazione dopo rimozione dei file vuoti per superare il vincolo degli strumenti sui file 0 byte e stabilire `.doc/` come verità logica aumentata.

### Allineamento (nota su file operativo)
- Rilevata modifica manuale in `scripts/setup.py`: aggiunta riga di nota "okkio questo e' un file importante".
- Azione Guardian: nessuna modifica applicata a file fuori da `.doc/`; registrato l’evento per tracciabilità e per evitare drift non intenzionale su script operativi.

### Allineamento TODO (legacy/drift)
- Aggiornato `TODO.md` (Fase A1): aggiunto task per rimuovere riferimenti operativi a monitor canonici legacy (script/batch non presenti nel tree corrente).

### Allineamento cross-reference
- Normalizzati i link interni ai canonici `.doc/*` in `READ.md`.
- Aggiornato riferimento retail contract in `TODO.md` a `PROJ.md#retail-contract`.
- Allineati riferimenti ai canonici in `CHLG.md` (PROJ/TECH/WPLN/TODO/DDIC/READ).
- Chiarito riferimento al file legacy Root in `WPLN.md`.

### Aggiornamento protocollo Guardian
- Aggiornate le specifiche operative a **ARCHITECTURAL GUARDIAN v1.4**.
- Aggiornati i file di servizio: `GUARDIAN_manual.md`, `CURRENT_STATE.md`.
 
 ### Correzione operativa (pre-check)
 - Aggiunta regola: in FASE 2, prima di proporre/applicare una patch, verificare che il file non sia già allineato al risultato desiderato; se lo è, non fare patch (evitare lavoro inutile).
 
### Allineamento a modifica applicativa
- Rilevata modifica in `src/db/migrate.py` (owner schema): aggiunti metadati di versione/last-updated dello schema.
- Allineato `DDIC.md`: aggiunta riga "Versione schema" derivata da `src/db/migrate.py`.

 ### Manuale Guardian: Dual-Agent + Persistenza
 - Aggiornato `GUARDIAN_manual.md`: introdotti Protocollo Dual-Agent (Esecutore/Critico), regole Anti-legacy/Anti-shortcut e sezione Persistenza/Attivazione (ripartenza via `CURRENT_STATE.md`).

 ### Windsurf: Guardian always-on (Workspace Rule)
 - Definita una Workspace Rule "ARCHITECTURAL GUARDIAN (Always-on)" per rendere Guardian la modalità predefinita del progetto in Windsurf.
 - Vincolo esplicito: stand-by (nessuna iniziativa sul codice) finché l'utente non comanda `guardian allinea`/`guardian sync`.
- Dual-Agent: modalità **sempre visibile** durante gli allineamenti (Esecutore/Critico in output).

### Allineamento A1 (evidenza batch legacy)
- Evidenza: rilevati riferimenti a monitor canonici legacy (script/batch non presenti nel tree corrente).
- Azione Guardian: aggiornati i canonici `.doc/` (solo documentazione) per tracciare il drift e mantenere coerenza del prompt di ripresa.

 ### Allineamento versione Guardian
 - Allineato `CURRENT_STATE.md` a **ARCHITECTURAL GUARDIAN v1.4** (coerente con `GUARDIAN_manual.md`).

 ### Allineamento post-commit (working tree pulito)
 - Evidenza: `git status --porcelain` non segnala modifiche (working tree pulito).
 - Azione Guardian: rimossi dai canonici `.doc/` i riferimenti a drift Root non più presente; `Next-Resume Prompt` riportato su Fase A1.

### Drift rilevato (working tree non pulito)
- Evidenza: `git status --porcelain` segnala modifica non committata su `pages/08_Lifecycle_Monitor.py`.
- Azione Guardian: aggiornato `CURRENT_STATE.md` per tracciare il drift e impostare il prossimo prompt su verifica diff + decisione commit/revert.

### Correzione A1 (refuso tool misnamed)
- Evidenza: rimosso manualmente `src/tools/db_status.y.py` (refuso/misnamed).
- Azione Guardian: riallineati i canonici `.doc/` per rimuovere la narrativa di shim e riportare come canonical `python -m src.tools.db_status`.

### Allineamento A1 (Policy A: boundary + deprecazioni operative)
- Azione Guardian: definito boundary definitivo `src/tools/` (tool canonici atomici) vs `scripts/` (ops/orchestratori + bootstrap) e aggiunta lista operativa KEEP vs DEPRECATE nei canonici `.doc/`.

 ### Correzione No-op policy (stabile su doc-only)
 - Azione Guardian: aggiornata la no-op policy in `GUARDIAN_manual.md` per usare `CODE_HEAD` (ultimo commit che modifica path fuori da `.doc/`) invece di `HEAD`.
 - Azione Guardian: aggiornato `CURRENT_STATE.md` introducendo `Last aligned CODE_HEAD` (campo usato dalla no-op policy) e mantenendo `Last aligned HEAD` solo come informazione.

 ### Decisione A1 (wrapper compatibilità in `scripts/`)
 - Evidenza: i wrapper `load_*_example.py` e `forced_exits` sono citati in README/TECH/runbook.
- Decisione: **KEEP** finché citati nella documentazione operativa; pianificare rimozione **solo dopo** migrazione delle istruzioni verso i comandi canonici `python -m src.tools.*`.

### Sync post commit ROOT+CODE
- Azione: registrata migrazione docs/runbook (golden path su src.tools.*) e commit della modifica manuale su pages/08_Lifecycle_Monitor.py.

### Migrazione runbook (golden path: `python -m src.tools.*`)
- Azione: aggiornati README/architettura/TECH per indicare come percorso primario i tool canonici `src.tools.*` invocabili via `python -m ...`.
- Azione: retrocessi i wrapper in `scripts/` a **compatibilità** (non golden path).

### Allineamento (modifica manuale committata)
- Evidenza: modifica manuale su `pages/08_Lifecycle_Monitor.py`.
- Azione: modifica inclusa e committata insieme alla migrazione runbook per mantenere working tree pulito.

### Allineamento A1 (rimozione wrapper compatibilità)
- Azione: rimossi i wrapper `scripts/find_forced_exits.py`, `scripts/show_forced_exits.py`, `scripts/show_forced_exit_details.py`, `scripts/load_ticker_mappings_example.py`, `scripts/load_universe_membership_example.py`.
- Azione: aggiornati i runbook/canonici per rimuovere i riferimenti ai wrapper; percorso operativo resta `python -m src.tools.*`.

### Sync post-commit (CODE_HEAD)
- Azione: aggiornato `CURRENT_STATE.md` (`Last aligned CODE_HEAD`) dopo la rimozione dei wrapper.

### Allineamento Root (A1 closure)
- Evidenza: aggiornati i root canonici `CHANGELOG.md`, `TECHNICAL_ARCHITECTURE.md`, `TODOLIST.md` per chiudere A1.
- Azione: esplicitata la scelta KEEP orchestratori in `scripts/` e hardening deprecazione `scripts/patch_persist_equity.py`.

### Sync post-commit (standard multi-OS e aggiornamento CODE_HEAD)
- Azione: registrato sync post-commit per standard multi-OS e aggiornamento CODE_HEAD.

### Allineamento multi-OS (placeholder `<PY>`)
- Evidenza: standardizzati comandi e help text per Windows (`py -3.14`) vs Linux/macOS (`python`) usando placeholder `<PY>`.
- Azione: allineati root canonici + help/docstring in codebase + canonici `.doc/`.
- Sync: aggiornato `CURRENT_STATE.md` (`Last aligned CODE_HEAD`) al nuovo valore dopo commit ROOT+CODE.

### Hardening Guardian (anti-drift doc↔code)
- Evidenza: individuato drift documentale su dettagli operativi (es. semantica di `session_key` per le session folders).
- Azione (docs-only): aggiornato `GUARDIAN_manual.md` per rendere obbligatorio il controllo anti-drift doc↔code quando i canonici descrivono chiavi deterministiche/naming/inventario `scripts/` (manuale + prompt + workspace rule).

### Governance — TODO=OPEN ONLY + `guardian allinea` (DocLint) (2026-01-19)
- Decisione: `TODO.md` è il **programma implementativo** (solo DA FARE). Nessun archivio prompt in TODO.
- Decisione: storico/evidenze (DONE/PARTIAL/decisioni) in `LOGBOOK.md`.
- Azione (docs-only): introdotta semantica distinta tra `guardian sync` (incrementale, con no-op) e `guardian allinea` (validazione forzata canonici, PASS/FAIL, possibile rigenerazione `TODO.md`/`CURRENT_STATE.md`).
- Azione (docs-only): aggiornato `WPLN.md` per rendere `guardian allinea` parte del DoD (DocLint PASS) e consolidare le evidenze run su `LOGBOOK.md`.

## 2026-01-20 — Programma canonici: NEWS-ALPHA history lane (N2/v0.2 + v0.2.1) + ripianificazione WI-001 (v0.2.2)

Evidenza (snapshot code inspection):
- `scripts/news_alpha.py` include command group `history` con `download|profile|fixtures`.
- Online guard: azioni online richiedono `--allow-online` **e** `--online` (fail-fast).
- Downloader hardening (v0.2.1): `NEWS_ALPHA_GDELT_BASE` + fallback schema http/https.
- Fixtures JSONL:
  - Events: `provider,stream,published_at,source,url,headline,body,tickers,gdelt{sql_date,actor1,actor2,event_code,event_root_code,avg_tone}`.
  - GKG: `provider,stream,published_at,source,url,headline,body,tickers,gdelt{themes,persons,organizations,tone}`.

Aggiornamenti canonici effettuati:
- Promossa history lane da Planned → Implemented in `PROJ.md`, `TECH.md`, `DDIC.md`, `WPLN.md`.
- Aggiunto DR-6 (News Dating Contract: AS-OF vs event_date) in `PROJ.md`.
- Aggiunto runbook `history` in `READ.md`.
- Rigenerato `TODO.md` come OPEN-only (WI-001) e riallineato `CURRENT_STATE.md` al nuovo `p0`.

Nota test:
- In un export ZIP senza dipendenze installate non è possibile attestare `main_test.py`/`pytest` come PASS.
  L’evidenza sopra è basata su ispezione del codice (read-only).

