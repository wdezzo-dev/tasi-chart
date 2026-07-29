# app.py
from datetime import datetime
import streamlit as st
import pandas as pd
from config import INTERVALS, DEFAULT_INTERVAL
from data_manager import full_refresh, update_interval, init_db, smart_update_all, get_last_candle_times
from data_loader import load_table
from matcher import (match_within_interval, match_across_intervals, match_universal,
                     add_interpretation_column, get_stock_report, format_report_to_html,
                     TAB_KEYS, TAB_NAMES)

st.set_page_config(page_title="المحلل الرقمي - تاسي", layout="wide")
init_db()

st.markdown("""
    <style>
    body, .stApp { direction: rtl; text-align: right; }
    th { text-align: center !important; font-size: 14px; background-color: #2e3035 !important; color: white !important;}
    td { text-align: center !important; font-size: 13px; font-weight: bold;}
    table { width: 100%; margin-bottom: 20px;}
    .stButton>button { border-radius: 8px; font-weight: bold; }
    div[data-testid="stHorizontalBlock"] > div:first-child { gap: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 شاشة المحلل الرقمي (TASI)")
st.caption("🕐 آخر تحديث: " + st.session_state.get('last_update', '—'))

# Interval selector
interval_labels = {'1h': '⏱️ 1 ساعة', '4h': '⏰ 4 ساعات', '1d': '📅 يومي'}
col_int, col_btn = st.columns([1, 1])
with col_int:
    selected_interval = st.segmented_control(
        "الفاصل الزمني",
        options=INTERVALS,
        default=DEFAULT_INTERVAL,
        format_func=lambda x: interval_labels[x],
        key="interval_selector"
    )
with col_btn:
    if st.button("🔄 تحديث البيانات"):
        with st.spinner("جاري التحقق من البيانات..."):
            results = smart_update_all()
        st.cache_data.clear()
        emoji = {'1h': '⏱️', '4h': '⏰', '1d': '📅'}
        any_updated = False
        for interval, msg in results.items():
            e = emoji.get(interval, '')
            if 'تم التحديث' in msg:
                st.success(f"{e} {interval}: {msg}")
                any_updated = True
            elif 'لا توجد' in msg:
                st.info(f"{e} {interval}: {msg}")
            else:
                st.warning(f"{e} {interval}: {msg}")
        if any_updated:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            st.session_state['last_update'] = now_str
            st.success("✅ تم تحديث البيانات بنجاح!")
        st.rerun()

# Status bar: last candle times
from time_utils import now_riyadh
candle_times = get_last_candle_times()
_status_cols = st.columns(3)
icons = {'1h': '⏱️', '4h': '⏰', '1d': '📅'}
labels = {'1h': 'آخر شمعة ساعة', '4h': 'آخر شمعة ٤ ساعات', '1d': 'آخر شمعة يوم'}
now_rt = now_riyadh()
for i, interval in enumerate(INTERVALS):
    raw = candle_times.get(interval)
    display = '—'
    if raw:
        try:
            if interval == '1d':
                candle_dt = datetime.fromisoformat(raw).date() if 'T' in raw else datetime.strptime(raw, '%Y-%m-%d').date()
                diff = (now_rt.date() - candle_dt).days
                if diff == 0:
                    display = 'اليوم'
                elif diff == 1:
                    display = 'أمس ' + candle_dt.strftime('%Y/%m/%d')
                else:
                    display = candle_dt.strftime('%Y/%m/%d')
            else:
                candle_dt = datetime.fromisoformat(raw)
                if candle_dt <= now_rt:
                    display = candle_dt.strftime('%Y/%m/%d %H:%M')
                else:
                    display = '— (غير مكتملة)'
        except Exception:
            display = raw[:16]
    _status_cols[i].markdown(
        f"<div style='font-size:13px; color:#aaa; line-height:1.6;'>{icons[interval]} {labels[interval]}: <b style='color:#ddd;'>{display}</b></div>",
        unsafe_allow_html=True
    )

# Load indicators for selected interval from Parquet
df1 = load_table(selected_interval, 1)
df2 = load_table(selected_interval, 2)
df3 = load_table(selected_interval, 3)
df4 = load_table(selected_interval, 4)
df5 = load_table(selected_interval, 5)

# ================== دوال التلوين ==================

def style_match_row(row):
    styles = [''] * len(row)
    for i, col in enumerate(row.index):
        val = row[col]
        if col == 'السعر' and isinstance(val, (int, float)):
            styles[i] = 'font-weight: bold;'
        elif col == 'التطابق' and isinstance(val, (int, float)):
            if val >= 4:
                styles[i] = 'background-color: #0b5030; color: white; font-weight: bold;'
            elif val == 3:
                styles[i] = 'background-color: #1b8a53; color: white; font-weight: bold;'
            elif val == 2:
                styles[i] = 'background-color: #5ac48e; color: black;'
            else:
                styles[i] = 'color: #666;'
        elif isinstance(val, str) and val.startswith('#'):
            try:
                rank = int(val[1:])
                if rank == 1:
                    styles[i] = 'background-color: #0b5030; color: white; font-weight: bold;'
                elif rank <= 3:
                    styles[i] = 'background-color: #1b8a53; color: white;'
                elif rank <= 5:
                    styles[i] = 'background-color: #5ac48e; color: black;'
                elif rank <= 10:
                    styles[i] = 'background-color: #e8f5e9; color: black;'
                else:
                    styles[i] = 'color: #999;'
            except ValueError:
                pass
        elif val is None or (isinstance(val, str) and val == '—'):
            styles[i] = 'color: #666;'
    return styles

def style_table1(row):
    styles = [''] * len(row)
    price = row['السعر'] if pd.notna(row['السعر']) else 0
    for i, col in enumerate(row.index):
        if 'المتوسط' in col and col != 'قيمة المتوسط' and pd.notna(row[col]) and row[col] != 0:
            dev = ((price - row[col]) / row[col]) * 100
            if dev > 5: styles[i] = 'background-color: #0b5030; color: white;'
            elif dev > 2: styles[i] = 'background-color: #1b8a53; color: white;'
            elif dev > 0: styles[i] = 'background-color: #5ac48e; color: black;'
            elif dev < -5: styles[i] = 'background-color: #7b161c; color: white;'
            elif dev < -2: styles[i] = 'background-color: #c92f39; color: white;'
            elif dev < 0: styles[i] = 'background-color: #e57373; color: black;'
        elif col == 'الإيجابي' and row[col] > 0: styles[i] = 'background-color: #0b5030; color: white;'
        elif col == 'السلبي' and row[col] > 0: styles[i] = 'background-color: #7b161c; color: white;'
    return styles

def style_general(row):
    styles = [''] * len(row)
    for i, col in enumerate(row.index):
        val = row[col]
        if isinstance(val, str):
            if val in ['إيجابي', 'تشبع بيع', 'أعلى من القيمة']:
                styles[i] = 'background-color: #0b5030; color: white;'
            elif val in ['سلبي', 'تشبع شراء', 'أدنى من القيمة']:
                styles[i] = 'background-color: #7b161c; color: white;'
        elif col == 'الإيجابي' and val > 0: styles[i] = 'background-color: #0b5030; color: white;'
        elif col == 'السلبي' and val > 0: styles[i] = 'background-color: #7b161c; color: white;'
        elif isinstance(val, (int, float)) and col not in ['السعر', 'قيمة المتوسط', 'الإيجابي', 'السلبي', 'Aroon Up', 'Aroon Down']:
            if val > 0: styles[i] = 'color: #1b8a53;'
            elif val < 0: styles[i] = 'color: #c92f39;'
    return styles

def render_tab(df, style_func, tab_key):
    if df.empty:
        st.warning("لا توجد بيانات متاحة لهذا الفاصل.")
        return
    col_sort, _ = st.columns([4, 4])
    with col_sort:
        sort_choice = st.radio(
            "فرز الجدول حسب:",
            ["الافتراضي", "🟢 الإيجابي (تنازلي)", "🔴 السلبي (تنازلي)"],
            horizontal=True, key=f"sort_{tab_key}_{selected_interval}"
        )
    if sort_choice == "🟢 الإيجابي (تنازلي)":
        df_sorted = df.sort_values(by=['الإيجابي', 'السلبي', 'الرمز'], ascending=[False, True, True]).reset_index(drop=True)
    elif sort_choice == "🔴 السلبي (تنازلي)":
        df_sorted = df.sort_values(by=['السلبي', 'الإيجابي', 'الرمز'], ascending=[False, True, True]).reset_index(drop=True)
    else:
        df_sorted = df.copy()
    html = df_sorted.style.apply(style_func, axis=1).to_html(index=False)
    st.markdown(
        f'<div style="overflow-x: auto; overflow-y: auto; max-height: 600px; width: 100%; border: 1px solid #333; border-radius: 4px;">{html}</div>',
        unsafe_allow_html=True
    )

# ================== أفضل التطابقات ==================

with st.expander("🔝 أفضل التطابقات", expanded=False):
    match_mode = st.radio(
        "نظرة عامة:",
        ["ضمن الفترة", "عبر الفترات", "شامل"],
        horizontal=True, key="match_mode"
    )

    col1, col2, col3, _ = st.columns([2, 2, 2, 4])

    if match_mode == "ضمن الفترة":
        with col1:
            mm_interval = st.selectbox(
                "الفترة", INTERVALS,
                index=INTERVALS.index(selected_interval),
                format_func=lambda x: {'1h': '1h', '4h': '4h', '1d': '1d'}[x],
                key="mm_interval"
            )
        with col2:
            mm_tabs = st.multiselect(
                "الجداول",
                options=list(range(1, 6)),
                default=[3, 4, 5],
                format_func=lambda x: f"ط{x} {TAB_NAMES[x]}",
                key="mm_tabs"
            )
        with col3:
            mm_top_n = st.number_input("عدد الأسهم", min_value=5, max_value=50, value=20, key="mm_top_n")
        mm_min_match = st.slider("حد التطابق (على الأقل)", 1, len(mm_tabs) if mm_tabs else 1,
                                  min(2, len(mm_tabs)) if mm_tabs else 1, key="mm_min_match")

        if mm_tabs and mm_min_match <= len(mm_tabs):
            result = match_within_interval(mm_interval, mm_tabs, mm_top_n, mm_min_match)

    elif match_mode == "عبر الفترات":
        with col1:
            mm_tab = st.selectbox(
                "الجدول", list(range(1, 6)),
                format_func=lambda x: f"ط{x} {TAB_NAMES[x]}",
                key="mm_tab"
            )
        with col2:
            mm_intervals = st.multiselect(
                "الفترات", INTERVALS, default=INTERVALS,
                format_func=lambda x: {'1h': '1h', '4h': '4h', '1d': '1d'}[x],
                key="mm_intervals"
            )
        with col3:
            mm_top_n2 = st.number_input("عدد الأسهم", min_value=5, max_value=50, value=20, key="mm_top_n2")
        mm_min_match2 = st.slider("حد التطابق (على الأقل)", 1, len(mm_intervals) if mm_intervals else 1,
                                   min(2, len(mm_intervals)) if mm_intervals else 1, key="mm_min_match2")

        if mm_intervals and mm_min_match2 <= len(mm_intervals):
            result = match_across_intervals(mm_tab, mm_intervals, mm_top_n2, mm_min_match2)

    else:
        with col1:
            mm_tabs_u = st.multiselect(
                "الجداول", list(range(1, 6)), default=[3, 4, 5],
                format_func=lambda x: f"ط{x} {TAB_NAMES[x]}",
                key="mm_tabs_u"
            )
        with col2:
            mm_intervals_u = st.multiselect(
                "الفترات", INTERVALS, default=INTERVALS,
                format_func=lambda x: {'1h': '1h', '4h': '4h', '1d': '1d'}[x],
                key="mm_intervals_u"
            )
        with col3:
            mm_top_n3 = st.number_input("عدد الأسهم", min_value=5, max_value=50, value=20, key="mm_top_n3")
        mm_min_match_i = st.slider("حد تطابق الفترات", 1, len(mm_intervals_u) if mm_intervals_u else 1,
                                    min(2, len(mm_intervals_u)) if mm_intervals_u else 1, key="mm_min_match_i")
        mm_min_match_t = st.slider("حد تطابق الجداول", 1, len(mm_tabs_u) if mm_tabs_u else 1,
                                    min(2, len(mm_tabs_u)) if mm_tabs_u else 1, key="mm_min_match_t")

        if mm_tabs_u and mm_intervals_u and mm_min_match_i <= len(mm_intervals_u) and mm_min_match_t <= len(mm_tabs_u):
            result = match_universal(mm_tabs_u, mm_intervals_u, mm_top_n3, mm_min_match_i, mm_min_match_t)

    # ================== عرض نتائج التطابق ==================

    if 'result' in locals() and not result.empty:
        total_stocks = result.shape[0]

        show_interp = False
        if match_mode == "ضمن الفترة" and mm_tabs:
            result = add_interpretation_column(result, mm_interval, mm_tabs)
            tabs_for_report = mm_tabs
            interp_interval = mm_interval
            show_interp = True
        elif match_mode == "شامل" and mm_tabs_u:
            rep_int = mm_intervals_u[0] if mm_intervals_u else '1h'
            result = add_interpretation_column(result, rep_int, mm_tabs_u)
            tabs_for_report = mm_tabs_u
            interp_interval = rep_int
            show_interp = True

        best_count = int(result['التطابق'].iloc[0])
        best_ticker = result.iloc[0]['الرمز']
        best_name = result.iloc[0]['الاسم']
        avg_match = float(result['التطابق'].mean())

        st.markdown(f"""
        <div style="background:#1e2a1e; padding:12px 16px; border-radius:8px; margin-bottom:8px; border:1px solid #2a4a2a;">
          <div style="font-size:16px; font-weight:bold; margin-bottom:6px;">✅ {total_stocks} سهم {'يتطابق' if total_stocks == 1 else 'تتطابق'} مع المعايير المحددة</div>
          <div style="display:flex; gap:20px; font-size:14px; color:#ccc;">
            <span>🏆 الأكثر تطابقاً: <b style="color:white;">{best_ticker}</b> ({best_name}) — <b style="color:#5ac48e;">{best_count}</b> من {result.shape[1] - 4}</span>
            <span>📊 متوسط التطابق: <b style="color:#5ac48e;">{avg_match:.1f}</b></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        styled = result.style.apply(style_match_row, axis=1)
        st.markdown(styled.to_html(index=False), unsafe_allow_html=True)

        if show_interp:
            st.markdown("---")
            st.markdown("##### 📋 تقرير مفصل عن السهم")
            report_tickers = result['الرمز'].tolist()
            selected_ticker = st.selectbox(
                "اختر السهم لعرض التقرير:", report_tickers,
                format_func=lambda x: f"{x} ({result[result['الرمز'] == x].iloc[0].get('الاسم', '')})",
                key="report_ticker"
            )
            match_row = result[result['الرمز'] == selected_ticker].iloc[0]
            report = get_stock_report(selected_ticker, interp_interval, tabs_for_report, TAB_KEYS, match_row)
            st.markdown(format_report_to_html(report), unsafe_allow_html=True)

    elif 'result' in locals() and result.empty:
        st.info("لا توجد أسهم تطابق المعايير المحددة. حاول تقليل حد التطابق.")

# ================== عرض الواجهة ==================
try:
    if df1.empty:
        st.warning("⚠️ لا توجد مؤشرات محفوظة. اضغط على زر **تحديث البيانات** لتحميل بيانات السوق وحساب المؤشرات.")
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "1. المتوسطات", "2. حالة المؤشرات",
            "3. الإشارات الفنية", "4. تشبع البيع والشراء", "5. ايشيموكو"
        ])
        with tab1: render_tab(df1, style_table1, "tab1")
        with tab2: render_tab(df2, style_general, "tab2")
        with tab3: render_tab(df3, style_general, "tab3")
        with tab4: render_tab(df4, style_general, "tab4")
        with tab5: render_tab(df5, style_general, "tab5")
except Exception as e:
    st.error(f"حدث خطأ: {e}")
