import pandas as pd
from data_loader import load_table

TAB_KEYS = {
    1: 'ط١ المتوسطات',
    2: 'ط٢ المؤشرات',
    3: 'ط٣ الإشارات',
    4: 'ط٤ التشبع',
    5: 'ط٥ ايشيموكو',
}

TAB_SHORT_NAMES = {
    1: 'المتوسطات',
    2: 'المؤشرات',
    3: 'الإشارات',
    4: 'التشبع',
    5: 'ايشيموكو',
}

TAB_EXPLANATIONS = {
    1: 'السعر أعلى من المتوسطات → اتجاه صاعد',
    2: 'المؤشرات الفنية إيجابية → زخم شرائي',
    3: 'إشارات فنية إيجابية → اختراقات وتقاطعات',
    4: 'تشبع بيع → فرصة ارتفاع محتملة',
    5: 'ايشيموكو إيجابي → اتجاه صاعد',
}

TAB_POSITIVE_COLS = {
    1: ['المتوسط 3', 'المتوسط 5', 'المتوسط 10', 'المتوسط 20',
        'المتوسط 50', 'المتوسط 100', 'المتوسط 200'],
    2: ['Aroon Up', 'MACD', 'MACD Histogr', 'Parabolic SA',
        'CMF', 'PPO', 'ROC', 'EOM'],
    3: ['اختراق متوسط 1', 'تقاطع متوسطات', 'اختراق MACD', 'تقاطع MACD',
        'تقاطع Stochas', 'تقاطع Aroon', 'تقاطع ADX', 'غيمة جديدة',
        'اختراق الغيمة', 'اختراق Kijun', 'تقاطع Tenken',
        'انعكاس Parabl', 'فجوة سعرية'],
    4: ['RSI', 'Stochastic D', 'Stochastic K', 'StochRSI', 'CCI', 'MFI', 'W%R'],
    5: ['القيمة', 'السعر مع القيمة', 'Kijun', 'Tenken Sen'],
}

TAB_TOTAL_POSITIVE = {1: 7, 2: 11, 3: 13, 4: 7, 5: 4}

TAB_NAMES = TAB_SHORT_NAMES


def _get_top_n(df, n=20):
    if df.empty:
        return {}
    top = df.nlargest(n, 'الإيجابي')[['الرمز', 'الاسم', 'السعر', 'الإيجابي']]
    result = {}
    for rank, (_, row) in enumerate(top.iterrows(), 1):
        result[row['الرمز']] = {
            'الاسم': row.get('الاسم', ''),
            'السعر': row.get('السعر', 0),
            'rank': rank,
        }
    return result


def _get_name_price(ticker, interval, tab_idx):
    df = load_table(interval, tab_idx)
    if df.empty:
        return '', 0
    match = df[df['الرمز'] == ticker]
    if not match.empty:
        return match.iloc[0].get('الاسم', ''), match.iloc[0].get('السعر', 0)
    return '', 0


def _format_rank(rank_val):
    return f"#{int(rank_val)}" if rank_val and rank_val > 0 else None


def _check_positive(val, tab_idx, price=None):
    if pd.isna(val):
        return False
    if tab_idx == 1:
        return price is not None and isinstance(val, (int, float)) and val != 0 and price > val
    elif tab_idx == 4:
        return str(val) == 'تشبع بيع'
    else:
        return str(val) in ['إيجابي', 'أعلى من القيمة']


def _get_tab_row(ticker, interval, tab_idx):
    df = load_table(interval, tab_idx)
    if df.empty:
        return None
    match = df[df['الرمز'] == ticker]
    return match.iloc[0] if not match.empty else None


def get_tab_highlights(ticker, interval, tab_idx):
    row = _get_tab_row(ticker, interval, tab_idx)
    if row is None:
        return []
    cols = TAB_POSITIVE_COLS.get(tab_idx, [])
    if tab_idx == 1:
        price = row.get('السعر', 0)
        return [c for c in cols if _check_positive(row.get(c), tab_idx, price)]
    return [c for c in cols if _check_positive(row.get(c), tab_idx)]


def get_tab_positive_count(ticker, interval, tab_idx):
    row = _get_tab_row(ticker, interval, tab_idx)
    if row is None:
        return 0
    return int(row.get('الإيجابي', 0))


def build_interpretation(qualified_tab_indices):
    names = [TAB_SHORT_NAMES[t] for t in sorted(qualified_tab_indices)]
    if not names:
        return '—'
    if len(names) == 1:
        return f'قوة في {names[0]}'
    if len(names) == 2:
        return f'قوة في {names[0]} و{names[1]}'
    return 'قوة في ' + ' و'.join(names)


def get_qualified_tabs(result_row, tab_indices):
    qualified = []
    for ti in tab_indices:
        col = TAB_KEYS.get(ti, f'ط{ti}')
        val = result_row.get(col)
        if val is not None and pd.notna(val):
            qualified.append(ti)
    return qualified


def add_interpretation_column(result, interval, tab_indices):
    if result.empty:
        return result
    interpretations = []
    for _, row in result.iterrows():
        qualified = get_qualified_tabs(row, tab_indices)
        interpretations.append(build_interpretation(qualified))
    result['التفسير'] = interpretations
    cols = [c for c in result.columns if c != 'التفسير'] + ['التفسير']
    result = result[cols]
    return result


def get_stock_report(ticker, interval, tab_indices, match_tab_cols, match_row):
    """Return a dict with full details for a stock's report."""
    report = {'ticker': ticker, 'interval': interval}
    tab_details = []
    total_qualified = 0

    for ti in tab_indices:
        col = TAB_KEYS.get(ti, f'ط{ti}')
        rank_val = match_row.get(col)
        if rank_val is None or pd.isna(rank_val):
            tab_details.append({
                'tab_idx': ti,
                'tab_name': TAB_KEYS[ti],
                'short_name': TAB_SHORT_NAMES[ti],
                'explanation': TAB_EXPLANATIONS[ti],
                'rank': None,
                'positive': 0,
                'total': TAB_TOTAL_POSITIVE[ti],
                'highlights': [],
                'qualified': False,
            })
            continue

        total_qualified += 1
        rank = int(str(rank_val).lstrip('#'))
        positive = get_tab_positive_count(ticker, interval, ti)
        highlights = get_tab_highlights(ticker, interval, ti)

        tab_details.append({
            'tab_idx': ti,
            'tab_name': TAB_KEYS[ti],
            'short_name': TAB_SHORT_NAMES[ti],
            'explanation': TAB_EXPLANATIONS[ti],
            'rank': rank,
            'positive': positive,
            'total': TAB_TOTAL_POSITIVE[ti],
            'highlights': highlights,
            'qualified': True,
        })

    report['tab_details'] = tab_details
    report['total_qualified'] = total_qualified
    report['total_tabs'] = len(tab_indices)

    name = match_row.get('الاسم', '')
    price = match_row.get('السعر', 0)
    if not name:
        name, price = _get_name_price(ticker, interval, tab_indices[0])
    report['name'] = name
    report['price'] = price

    return report


def format_report_to_html(report):
    """Convert report dict to an HTML string for display."""
    qualified = report['total_qualified']
    total = report['total_tabs']
    interval_label = {'1h': '1 ساعة', '4h': '4 ساعات', '1d': 'يومي'}.get(report['interval'], report['interval'])

    html = f"""
    <div style="direction:rtl; text-align:right; background:#1e1e1e; padding:16px; border-radius:8px; margin:12px 0; border:1px solid #333;">
      <div style="font-size:18px; font-weight:bold; margin-bottom:12px;">
        📋 تقرير سريع: {report['ticker']} ({report['name']}) — {interval_label}
      </div>
      <div style="margin-bottom:14px; color:#5ac48e;">
        ✅ مطابق في {qualified} من {total} جداول (ضمن أفضل 20)
      </div>
    """

    for td in report['tab_details']:
        if td['qualified']:
            color = '#0b5030' if td['rank'] == 1 else '#1b8a53' if td['rank'] <= 3 else '#5ac48e'
            highlights_str = ''
            if td['highlights']:
                hl_list = '، '.join(td['highlights'][:5])
                highlights_str = f'<div style="font-size:13px; color:#aaa; margin-top:2px;">إيجابيات: {hl_list}</div>'
            html += f"""
      <div style="display:flex; align-items:flex-start; padding:8px; margin-bottom:4px; background:#2a2a2a; border-radius:4px; border-right:3px solid {color};">
        <div style="min-width:120px; font-weight:bold;">{td['tab_name']}</div>
        <div style="min-width:30px; font-weight:bold; color:#5ac48e;">#{td['rank']}</div>
        <div style="flex:1;">
          <div>{td['positive']} من {td['total']} إيجابي — {td['explanation'].split('→')[1].strip() if '→' in td['explanation'] else td['explanation']}</div>
          {highlights_str}
        </div>
      </div>
            """
        else:
            html += f"""
      <div style="display:flex; align-items:center; padding:8px; margin-bottom:4px; background:#1a1a1a; border-radius:4px; color:#666;">
        <div style="min-width:120px; font-weight:bold;">{td['tab_name']}</div>
        <div style="min-width:30px;">—</div>
        <div style="flex:1;">{td['explanation']}</div>
      </div>
            """

    html += '</div>'
    return html


def match_within_interval(interval, tab_indices, top_n=20, min_match=2):
    tab_top = {}
    for ti in tab_indices:
        df = load_table(interval, ti)
        top = _get_top_n(df, top_n)
        if top:
            tab_top[ti] = top

    if not tab_top:
        return pd.DataFrame()

    all_tickers = set()
    for top in tab_top.values():
        all_tickers.update(top.keys())

    rows = []
    for ticker in all_tickers:
        match_count = 0
        rank_sum = 0
        name, price = '', 0
        row_data = {'الرمز': ticker}

        for ti in tab_indices:
            col = TAB_KEYS.get(ti, f'ط{ti}')
            if ti in tab_top and ticker in tab_top[ti]:
                r = tab_top[ti][ticker]['rank']
                row_data[col] = _format_rank(r)
                match_count += 1
                rank_sum += r
                if not name:
                    name = tab_top[ti][ticker].get('الاسم', '')
                    price = tab_top[ti][ticker].get('السعر', 0)
            else:
                row_data[col] = None

        if match_count >= min_match:
            if not name:
                name, price = _get_name_price(ticker, interval, tab_indices[0])
            row_data['الاسم'] = name
            row_data['السعر'] = price
            row_data['التطابق'] = match_count
            row_data['_score'] = rank_sum
            rows.append(row_data)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.sort_values(['التطابق', '_score'], ascending=[False, True])
    result = result.drop(columns=['_score'])
    result = result.reset_index(drop=True)
    result.index += 1

    tab_cols = [TAB_KEYS.get(ti, f'ط{ti}') for ti in tab_indices]
    cols = ['الرمز', 'الاسم', 'السعر'] + tab_cols + ['التطابق']
    return result[cols]


def match_across_intervals(tab_idx, intervals, top_n=20, min_match=2):
    interval_top = {}
    for interval in intervals:
        df = load_table(interval, tab_idx)
        top = _get_top_n(df, top_n)
        if top:
            interval_top[interval] = top

    if not interval_top:
        return pd.DataFrame()

    all_tickers = set()
    for top in interval_top.values():
        all_tickers.update(top.keys())

    rows = []
    for ticker in all_tickers:
        match_count = 0
        rank_sum = 0
        name, price = '', 0
        row_data = {'الرمز': ticker}

        for interval in intervals:
            if interval in interval_top and ticker in interval_top[interval]:
                r = interval_top[interval][ticker]['rank']
                row_data[interval] = _format_rank(r)
                match_count += 1
                rank_sum += r
                if not name:
                    name = interval_top[interval][ticker].get('الاسم', '')
                    price = interval_top[interval][ticker].get('السعر', 0)
            else:
                row_data[interval] = None

        if match_count >= min_match:
            if not name:
                name, price = _get_name_price(ticker, intervals[0], tab_idx)
            row_data['الاسم'] = name
            row_data['السعر'] = price
            row_data['التطابق'] = match_count
            row_data['_score'] = rank_sum
            rows.append(row_data)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.sort_values(['التطابق', '_score'], ascending=[False, True])
    result = result.drop(columns=['_score'])
    result = result.reset_index(drop=True)
    result.index += 1

    cols = ['الرمز', 'الاسم', 'السعر'] + list(intervals) + ['التطابق']
    return result[cols]


def match_universal(tab_indices, intervals, top_n=20, min_match_intervals=2, min_match_tabs=2):
    tab_qualified = {}

    for ti in tab_indices:
        interval_top = {}
        for interval in intervals:
            df = load_table(interval, ti)
            top = _get_top_n(df, top_n)
            if top:
                interval_top[interval] = top

        if not interval_top:
            continue

        all_tickers = set()
        for top in interval_top.values():
            all_tickers.update(top.keys())

        for ticker in all_tickers:
            count = 0
            ranks = []
            for interval in intervals:
                if interval in interval_top and ticker in interval_top[interval]:
                    count += 1
                    ranks.append(interval_top[interval][ticker]['rank'])
            if count >= min_match_intervals:
                avg_rank = sum(ranks) / len(ranks) if ranks else 0
                if ticker not in tab_qualified:
                    tab_qualified[ticker] = {}
                tab_qualified[ticker][ti] = avg_rank

    if not tab_qualified:
        return pd.DataFrame()

    rows = []
    for ticker, t_ranks in tab_qualified.items():
        if len(t_ranks) < min_match_tabs:
            continue

        name, price = '', 0
        row_data = {'الرمز': ticker}

        for ti in tab_indices:
            col = TAB_KEYS.get(ti, f'ط{ti}')
            if ti in t_ranks:
                row_data[col] = _format_rank(round(t_ranks[ti]))
            else:
                row_data[col] = None

        for ti in tab_indices:
            if name:
                break
            for interval in intervals:
                name, price = _get_name_price(ticker, interval, ti)
                if name:
                    break

        row_data['الاسم'] = name
        row_data['السعر'] = price
        row_data['التطابق'] = len(t_ranks)
        row_data['_score'] = sum(t_ranks.values())
        rows.append(row_data)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.sort_values(['التطابق', '_score'], ascending=[False, True])
    result = result.drop(columns=['_score'])
    result = result.reset_index(drop=True)
    result.index += 1

    tab_cols = [TAB_KEYS.get(ti, f'ط{ti}') for ti in tab_indices]
    cols = ['الرمز', 'الاسم', 'السعر'] + tab_cols + ['التطابق']
    return result[cols]
