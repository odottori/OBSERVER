# OBSERVER 2.0 — Documentazione codice

Questa è una vista **as-built** del codice (API + guide minime) generata con MkDocs + mkdocstrings.

- La **source of truth** del progetto resta nel docset canonico in `docs/` (PDR/PDD/spec/trace/gap).
- Questo sito è **derivato**: puoi rigenerarlo con un comando.

## Avvio (Windows / PowerShell)

```powershell
py -m pip install -r mkdocs\requirements-docs.txt
py .\scripts\serve_code_docs.py
```

## Refresh completo (docset + code docs)

```powershell
py .\scripts\build_all_docs.py
```
