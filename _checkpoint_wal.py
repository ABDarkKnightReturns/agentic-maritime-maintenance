"""One-shot WAL checkpoint — run while the app is stopped."""
import sys, sqlite3
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')
from storage.database import DB_PATH

conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
print(f"Checkpoint result: busy={result[0]} log={result[1]} checkpointed={result[2]}")
conn.execute("PRAGMA optimize")
conn.close()

import os
from pathlib import Path
wal = Path(str(DB_PATH) + "-wal")
shm = Path(str(DB_PATH) + "-shm")
db  = DB_PATH
print(f"DB:  {db.stat().st_size/1024:.1f} KB" if db.exists() else "DB missing")
print(f"WAL: {wal.stat().st_size/1024:.1f} KB" if wal.exists() else "WAL: gone (fully checkpointed)")
