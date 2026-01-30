# MOD-NEWS-ALPHA

**Registro canonico:** [MOD-NEWS-ALPHA](../registry/#mod-news-alpha)

- **Dominio:** Data+Signal
- **Livello:** RUN-GRADE
- **Entrypoint:** ``py scripts/news_alpha.py collect|run|status``
- **Codice:** ``src/news_alpha/*` + runner`
- **Output:** ``recs`, `sentiment_cache``
- **Gate minimi:** `--online` esplicito + audit rows
- **Gap derivati (nota):** degradano segnali/forecast se la freshness è scarsa

## Nota
Questa pagina è **derivata**: viene generata da `docs/010_MODULE_REGISTRY.md`.
