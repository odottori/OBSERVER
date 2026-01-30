from pathlib import Path
import re

path = Path(r"src/db/audit_store.py")
text = path.read_text(encoding="utf-8")

# Avoid double-patching
if "Backward compatibility: older equity curves may use open_positions" in text:
    print("OK: patch già presente in src/db/audit_store.py")
    raise SystemExit(0)

# Find the df['run_id'] assignment line and insert immediately after it (preserving indentation)
m = re.search(r'(?m)^(?P<indent>[ \t]*)df\["run_id"\]\s*=\s*str\(run_id\)\s*$', text)
if not m:
    m = re.search(r'(?m)^(?P<indent>[ \t]*)df\["run_id"\]\s*=\s*run_id\s*$', text)

if not m:
    raise SystemExit("ERROR: non trovo la riga df[\"run_id\"] = ... in src/db/audit_store.py")

indent = m.group("indent")

patch = f"""
{indent}# Backward compatibility: older equity curves may use open_positions.
{indent}if "positions" not in df.columns and "open_positions" in df.columns:
{indent}    df["positions"] = df["open_positions"]

{indent}# Derive invested if missing (equity = cash + invested).
{indent}if "invested" not in df.columns and "equity" in df.columns and "cash" in df.columns:
{indent}    import pandas as pd
{indent}    df["invested"] = pd.to_numeric(df["equity"], errors="coerce") - pd.to_numeric(df["cash"], errors="coerce")

{indent}# Normalize numeric fields
{indent}import pandas as pd
{indent}if "positions" in df.columns:
{indent}    df["positions"] = pd.to_numeric(df["positions"], errors="coerce").fillna(0).astype(int)
{indent}if "invested" in df.columns:
{indent}    df["invested"] = pd.to_numeric(df["invested"], errors="coerce").fillna(0.0).astype(float)
"""

# Insert patch right after the matched run_id line
insert_at = m.end()
text2 = text[:insert_at] + patch + text[insert_at:]

path.write_text(text2, encoding="utf-8")
print("OK: patched src/db/audit_store.py (open_positions -> positions + invested derivation)")
