"""Re-apply sql/23 (cfg.usp_AssembleConfiguredProduct, CREATE OR ALTER)."""
import re
import sys
from pathlib import Path

import pyodbc

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;'
      'Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;')
text = Path("sql/23_Create_Assemble_Configured_Product.sql").read_text(encoding="utf-8-sig")
cn = pyodbc.connect(CS, autocommit=True)
cur = cn.cursor()
for b in re.split(r"(?im)^\s*GO\s*$", text):
    if b.strip():
        cur.execute(b)
        while cur.nextset():
            pass
print("sql/23 applied")
