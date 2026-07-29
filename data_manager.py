# data_manager.py
import sqlite3
import json
import os
import pandas as pd
import yfinance as yf
from config import DB_NAME, SAUDI_TICKERS, INTERVALS, TARGET_COLS, CHUNK_SIZE, MAX_WORKERS
from datetime import datetime
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

CANDLE_TRACKER_PATH = "data/last_candle.json"

def _read_candle_tracker():
    if os.path.exists(CANDLE_TRACKER_PATH):
        with open(CANDLE_TRACKER_PATH) as f:
            return json.load(f)
    return {}

def _write_candle_tracker(tracker):
    os.makedirs("data", exist_ok=True)
    tmp = CANDLE_TRACKER_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tracker, f)
    os.replace(tmp, CANDLE_TRACKER_PATH)

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    conn = get_conn()
    for interval in INTERVALS:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS ohlcv_{interval} (
                ticker TEXT, datetime TEXT, open REAL, high REAL,
                low REAL, close REAL, volume REAL,
                PRIMARY KEY (ticker, datetime)
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS indicators_{interval} (
                table_id INTEGER, data TEXT, updated_at TEXT,
                PRIMARY KEY (table_id)
            )
        """)
    conn.commit()
    conn.close()

# ========== Batch Download ==========

def _chunk_tickers(tickers, size=None):
    if size is None:
        size = CHUNK_SIZE
    for i in range(0, len(tickers), size):
        yield tickers[i:i + size]

def _flatten_yfinance_batch(raw_df):
    """Convert yfinance MultiIndex batch result to unified OHLCV format"""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()
    
    date_col = 'Datetime' if 'Datetime' in raw_df.columns or ('Datetime', '') in raw_df.columns else 'Date'
    
    if isinstance(raw_df.columns, pd.MultiIndex):
        tickers_in_df = raw_df.columns.get_level_values(0).unique()
    else:
        single = raw_df.copy().reset_index()
        dcol = 'Datetime' if 'Datetime' in single.columns else 'Date'
        single = single.rename(columns={dcol: 'datetime', 'Open': 'open', 'High': 'high',
                                        'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        single['datetime'] = single['datetime'].astype(str)
        return single
    
    all_parts = []
    for ticker in tickers_in_df:
        df_t = raw_df[ticker].copy().reset_index()
        dcol = 'Datetime' if 'Datetime' in df_t.columns else 'Date'
        df_t = df_t.rename(columns={dcol: 'datetime', 'Open': 'open', 'High': 'high',
                                    'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        df_t['ticker'] = ticker
        df_t['datetime'] = df_t['datetime'].astype(str)
        all_parts.append(df_t[['ticker', 'datetime', 'open', 'high', 'low', 'close', 'volume']])
    
    return pd.concat(all_parts, ignore_index=True) if all_parts else pd.DataFrame()

def _download_chunk(ticker_chunk, interval, period, retries=2):
    """Download a chunk of tickers as a single yfinance batch"""
    for attempt in range(retries):
        try:
            raw = yf.download(
                ticker_chunk, period=period, interval=interval,
                group_by='ticker', threads=True, progress=False
            )
            if raw is not None and not raw.empty:
                return _flatten_yfinance_batch(raw)
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return pd.DataFrame()

def batch_download(interval, period, tickers=None):
    """Download all tickers in parallel chunks"""
    if tickers is None:
        tickers = SAUDI_TICKERS
    chunks = list(_chunk_tickers(tickers))
    all_dfs = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_download_chunk, c, interval, period): c for c in chunks}
        for f in as_completed(futures):
            result = f.result()
            if not result.empty:
                all_dfs.append(result)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# ========== Bulk Insert ==========

def _bulk_insert_ohlcv(conn, ohlcv_table, df):
    """Replace all data for the OHLCV table with new batch data"""
    if df.empty:
        return
    conn.execute(f"DELETE FROM {ohlcv_table}")
    # Split by ticker for efficient per-ticker storage
    for ticker in df['ticker'].unique():
        df_t = df[df['ticker'] == ticker].sort_values('datetime')
        if not df_t.empty:
            df_t.to_sql(ohlcv_table, conn, if_exists='append', index=False)

def _append_new_candles(conn, ohlcv_table, df):
    """Insert only new candles (not already in DB)"""
    if df.empty:
        return
    for ticker in df['ticker'].unique():
        existing = set(pd.read_sql_query(
            f"SELECT datetime FROM {ohlcv_table} WHERE ticker = '{ticker}'", conn
        )['datetime'].tolist())
        df_t = df[df['ticker'] == ticker]
        new_df = df_t[~df_t['datetime'].isin(existing)]
        if not new_df.empty:
            new_df.to_sql(ohlcv_table, conn, if_exists='append', index=False)

# ========== Resample ==========

def _resample_1h_to_4h(conn):
    conn.execute("DELETE FROM ohlcv_4h")
    for ticker in SAUDI_TICKERS:
        df = pd.read_sql_query(
            f"SELECT * FROM ohlcv_1h WHERE ticker = '{ticker}' ORDER BY datetime ASC", conn)
        if df.empty:
            continue
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        ohlc = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        df_4h = df.resample('4h', label='right', closed='right').agg(ohlc).dropna()
        if df_4h.empty:
            continue
        df_4h = df_4h.reset_index()
        df_4h['ticker'] = ticker
        df_4h['datetime'] = df_4h['datetime'].astype(str)
        df_4h.to_sql('ohlcv_4h', conn, if_exists='append', index=False)

# ========== Main Data Operations ==========

def fetch_initial_data():
    conn = get_conn()
    
    print("Downloading 1h data (1 year) for all tickers...")
    df_1h = batch_download('1h', '1y')
    if not df_1h.empty:
        print(f"  Got {len(df_1h)} 1h candles")
        _bulk_insert_ohlcv(conn, 'ohlcv_1h', df_1h)
    
    print("Resampling 1h -> 4h...")
    _resample_1h_to_4h(conn)
    
    print("Downloading 1d data (2 years) for all tickers...")
    df_1d = batch_download('1d', '2y')
    if not df_1d.empty:
        print(f"  Got {len(df_1d)} 1d candles")
        _bulk_insert_ohlcv(conn, 'ohlcv_1d', df_1d)
    
    conn.commit()
    conn.close()
    print("Initial data fetch complete.")

def update_interval(interval):
    conn = get_conn()
    ohlcv_table = f'ohlcv_{interval}'
    
    if interval == '1h':
        df_new = batch_download('1h', '5d')
        if not df_new.empty:
            _append_new_candles(conn, ohlcv_table, df_new)
        _resample_1h_to_4h(conn)
    elif interval == '4h':
        _resample_1h_to_4h(conn)
    elif interval == '1d':
        df_new = batch_download('1d', '5d')
        if not df_new.empty:
            _append_new_candles(conn, ohlcv_table, df_new)
    
    conn.commit()
    conn.close()
    calculate_and_save_indicators(interval)

def calculate_and_save_indicators(interval):
    from analyzer import calculate_all_tables
    from config import COMPANY_NAMES
    conn = get_conn()
    ohlcv_table = f'ohlcv_{interval}'
    ind_table = f'indicators_{interval}'
    
    all_data = {1: [], 2: [], 3: [], 4: [], 5: []}
    max_dt = None

    for ticker in SAUDI_TICKERS:
        df = pd.read_sql_query(
            f"SELECT * FROM {ohlcv_table} WHERE ticker = '{ticker}' ORDER BY datetime ASC", conn)
        if df.empty:
            continue
        ticker_max = df['datetime'].max()
        if pd.notna(ticker_max):
            if max_dt is None or str(ticker_max) > str(max_dt):
                max_dt = ticker_max
        try:
            results = calculate_all_tables(df, ticker)
        except Exception:
            continue
        if not results:
            continue
        t1, t2, t3, t4, t5 = results
        for t in [t1, t2, t3, t4, t5]:
            t['الاسم'] = COMPANY_NAMES.get(ticker, ticker)
        all_data[1].append(t1); all_data[2].append(t2); all_data[3].append(t3)
        all_data[4].append(t4); all_data[5].append(t5)
    
    conn.execute(f"DELETE FROM {ind_table}")
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for table_id in range(1, 6):
        if not all_data[table_id]:
            continue
        df = pd.DataFrame(all_data[table_id])
        cols = TARGET_COLS[table_id]
        for c in cols:
            if c not in df.columns:
                df[c] = '-'
        df = df[cols]
        conn.execute(
            f"INSERT INTO {ind_table} (table_id, data, updated_at) VALUES (?, ?, ?)",
            (table_id, df.to_json(orient='records', force_ascii=False), now))
        parquet_dir = f"data/{interval}"
        os.makedirs(parquet_dir, exist_ok=True)
        df.to_parquet(f"{parquet_dir}/table_{table_id}.parquet", compression="snappy", index=False)
    # ACID: only write tracker after all 5 Parquet files are written
    if max_dt is not None:
        tracker = _read_candle_tracker()
        tracker[interval] = str(max_dt)
        _write_candle_tracker(tracker)
    conn.commit()
    conn.close()

def get_indicators(interval):
    conn = get_conn()
    ind_table = f'indicators_{interval}'
    results = {1: pd.DataFrame(), 2: pd.DataFrame(), 3: pd.DataFrame(),
               4: pd.DataFrame(), 5: pd.DataFrame()}
    rows = pd.read_sql_query(f"SELECT * FROM {ind_table} ORDER BY table_id", conn)
    conn.close()
    for _, row in rows.iterrows():
        tid = row['table_id']
        df = pd.read_json(StringIO(row['data']), orient='records')
        if not df.empty:
            results[tid] = df
    return results[1], results[2], results[3], results[4], results[5]

def full_refresh():
    init_db()
    fetch_initial_data()
    for interval in INTERVALS:
        print(f"Calculating indicators for {interval}...")
        calculate_and_save_indicators(interval)
    print("Full refresh complete!")


# ========== Smart Incremental Updates ==========

def _get_latest_ohlcv_datetime(conn, interval):
    try:
        result = conn.execute(f"SELECT MAX(datetime) FROM ohlcv_{interval}").fetchone()
        return result[0] if result and result[0] else None
    except sqlite3.OperationalError:
        return None


def _count_new_1h_since(conn, since_dt_str):
    if since_dt_str is None:
        return 0
    result = conn.execute(
        "SELECT COUNT(DISTINCT datetime) FROM ohlcv_1h WHERE datetime > ?", (since_dt_str,)
    ).fetchone()
    return result[0] if result else 0


def _should_resample_4h(conn):
    from time_utils import is_market_day, now_riyadh
    latest_4h = _get_latest_ohlcv_datetime(conn, '4h')
    if latest_4h is None:
        return True
    new_count = _count_new_1h_since(conn, latest_4h)
    if new_count >= 4:
        return True
    now = now_riyadh()
    if new_count >= 1 and (not is_market_day(now) or now.hour >= 16):
        return True
    return False


def get_last_candle_times():
    """Return dict with latest candle datetime for each interval from tracker."""
    tracker = _read_candle_tracker()
    return {interval: tracker.get(interval) for interval in INTERVALS}


def smart_update_all():
    from time_utils import can_fetch_1h, can_fetch_1d
    conn = get_conn()
    results = {}
    updated_intervals = []

    ok, reason = can_fetch_1h()
    if ok:
        df_new = batch_download('1h', '5d')
        if not df_new.empty:
            _append_new_candles(conn, 'ohlcv_1h', df_new)
            results['1h'] = 'تم التحديث ✓'
            updated_intervals.append('1h')
        else:
            results['1h'] = 'لا توجد بيانات جديدة'
        conn.commit()
    else:
        results['1h'] = reason

    ok_h = 'تم التحديث' in results.get('1h', '')
    if ok_h or _should_resample_4h(conn):
        _resample_1h_to_4h(conn)
        conn.commit()
        results['4h'] = 'تم التحديث ✓'
        updated_intervals.append('4h')

    ok, reason = can_fetch_1d()
    if ok:
        df_new = batch_download('1d', '5d')
        if not df_new.empty:
            _append_new_candles(conn, 'ohlcv_1d', df_new)
            results['1d'] = 'تم التحديث ✓'
            updated_intervals.append('1d')
        else:
            results['1d'] = 'لا توجد بيانات جديدة'
        conn.commit()
    else:
        results['1d'] = reason

    conn.close()

    for interval in updated_intervals:
        calculate_and_save_indicators(interval)

    return results
