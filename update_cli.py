# update_cli.py — standalone CLI updater for cron / GitHub Actions
# Run: python update_cli.py
from data_manager import (init_db, fetch_initial_data, calculate_and_save_indicators,
                          batch_download, _append_new_candles, _resample_1h_to_4h,
                          _get_latest_ohlcv_datetime, get_conn)
from config import INTERVALS


def update():
    init_db()

    conn = get_conn()
    has_data = _get_latest_ohlcv_datetime(conn, '1h') is not None
    conn.close()

    if not has_data:
        print("First run: fetching all data...")
        fetch_initial_data()
    else:
        print("Incremental update: downloading 5 days of 1h and 1d...")
        conn = get_conn()

        df_1h = batch_download('1h', '5d')
        if not df_1h.empty:
            print(f"  Got {len(df_1h)} new 1h candles")
            _append_new_candles(conn, 'ohlcv_1h', df_1h)
        else:
            print("  No new 1h data")

        _resample_1h_to_4h(conn)
        print("  4h resampled from 1h")

        df_1d = batch_download('1d', '5d')
        if not df_1d.empty:
            print(f"  Got {len(df_1d)} new 1d candles")
            _append_new_candles(conn, 'ohlcv_1d', df_1d)
        else:
            print("  No new 1d data")

        conn.commit()
        conn.close()

    for interval in INTERVALS:
        print(f"Calculating indicators for {interval}...")
        calculate_and_save_indicators(interval)

    print("Update complete!")


if __name__ == "__main__":
    update()
