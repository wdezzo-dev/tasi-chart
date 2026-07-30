# update_cli.py — standalone CLI updater for cron / GitHub Actions
# Run: python update_cli.py [--intervals 1d,4h]
import sys
import argparse
from data_manager import (init_db, fetch_initial_data, calculate_and_save_indicators,
                          batch_download, _append_new_candles, _resample_1h_to_4h,
                          _get_latest_ohlcv_datetime, _get_tickers_needing_full_data,
                          _should_resample_4h, get_conn)
from config import INTERVALS
from datetime import datetime


def update(intervals=None):
    if intervals is None:
        intervals = INTERVALS
    force = intervals != INTERVALS

    init_db()

    conn = get_conn()
    has_data = _get_latest_ohlcv_datetime(conn, '1h') is not None
    conn.close()

    if not has_data and set(intervals) == set(INTERVALS):
        print("=" * 50)
        print("First run: fetching all data for all tickers...")
        print("=" * 50)
        fetch_initial_data()
    else:
        print("=" * 50)
        print(f"Incremental Update — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if force:
            print(f"Selected intervals: {', '.join(intervals)}")
        print("=" * 50)
        conn = get_conn()

        # ---------- 1h ----------
        if '1h' in intervals:
            need_full = _get_tickers_needing_full_data(conn, '1h')
            if need_full:
                print(f"\n[1h] {len(need_full)} tickers need full history (< 200 candles)")
                print(f"[1h] Downloading 1y history for {len(need_full)} tickers...")
                df_full = batch_download('1h', '1y', tickers=need_full)
                if not df_full.empty:
                    got = len(df_full)
                    _append_new_candles(conn, 'ohlcv_1h', df_full)
                    print(f"[1h] Got {got} candles from full-history download")
                conn.commit()
            else:
                print(f"\n[1h] All tickers have sufficient data")

            print(f"[1h] Downloading 5d incremental data...")
            df_1h = batch_download('1h', '5d')
            if not df_1h.empty:
                prev = conn.execute("SELECT COUNT(*) FROM ohlcv_1h").fetchone()[0]
                _append_new_candles(conn, 'ohlcv_1h', df_1h)
                total = conn.execute("SELECT COUNT(*) FROM ohlcv_1h").fetchone()[0]
                added = total - prev
                print(f"[1h] Added {added} new candles (total: {total})")
            else:
                print("[1h] No new 1h data")

        # ---------- 4h ----------
        if '4h' in intervals:
            if force or _should_resample_4h(conn):
                print(f"\n[4h] Resampling from 1h...")
                _resample_1h_to_4h(conn)
                print("[4h] Resample complete")
            else:
                print(f"\n[4h] Skipped — waiting for 4 new 1h candles or market close")

        # ---------- 1d ----------
        if '1d' in intervals:
            need_full = _get_tickers_needing_full_data(conn, '1d')
            if need_full:
                print(f"\n[1d] {len(need_full)} tickers need full history (< 200 candles)")
                print(f"[1d] Downloading 2y history for {len(need_full)} tickers...")
                df_full = batch_download('1d', '2y', tickers=need_full)
                if not df_full.empty:
                    got = len(df_full)
                    _append_new_candles(conn, 'ohlcv_1d', df_full)
                    print(f"[1d] Got {got} candles from full-history download")
                conn.commit()
            else:
                print(f"\n[1d] All tickers have sufficient data")

            print(f"[1d] Downloading 5d incremental data...")
            df_1d = batch_download('1d', '5d')
            if not df_1d.empty:
                prev = conn.execute("SELECT COUNT(*) FROM ohlcv_1d").fetchone()[0]
                _append_new_candles(conn, 'ohlcv_1d', df_1d)
                total = conn.execute("SELECT COUNT(*) FROM ohlcv_1d").fetchone()[0]
                added = total - prev
                print(f"[1d] Added {added} new candles (total: {total})")
            else:
                print("[1d] No new 1d data")

        conn.commit()
        conn.close()

    print("\n" + "-" * 50)
    for interval in intervals:
        print(f"Calculating indicators for {interval}...")
        calculate_and_save_indicators(interval)

    print("\n" + "=" * 50)
    print("Update complete!")
    print("=" * 50)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Update TASI technical analysis data')
    parser.add_argument('--intervals', '-i',
                        help='Comma-separated intervals to update (e.g. 1d,4h)')
    args = parser.parse_args()

    if args.intervals:
        selected = [i.strip() for i in args.intervals.split(',')]
        invalid = [i for i in selected if i not in INTERVALS]
        if invalid:
            print(f"Invalid intervals: {invalid}. Valid options: {INTERVALS}")
            sys.exit(1)
        update(selected)
    else:
        update()
