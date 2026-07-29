import sqlite3
from io import StringIO
import os
import pandas as pd
from config import DB_NAME, INTERVALS

def convert_db_to_parquet():
    conn = sqlite3.connect(DB_NAME)

    for interval in INTERVALS:
        ind_table = f"indicators_{interval}"
        parquet_dir = f"data/{interval}"
        os.makedirs(parquet_dir, exist_ok=True)

        rows = conn.execute(f"SELECT * FROM {ind_table} ORDER BY table_id").fetchall()
        if not rows:
            print(f"  No data found for {interval}, skipping.")
            continue

        for row in rows:
            table_id = row[0]
            data_blob = row[1]
            if not data_blob:
                continue
            df = pd.read_json(StringIO(data_blob), orient="records")
            if df.empty:
                continue
            path = f"{parquet_dir}/table_{table_id}.parquet"
            df.to_parquet(path, compression="snappy", index=False)
            print(f"  Written: {path} ({len(df)} rows)")

    conn.close()
    print("Conversion complete.")

if __name__ == "__main__":
    convert_db_to_parquet()
