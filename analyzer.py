# analyzer.py
import pandas as pd
import pandas_ta

def calculate_all_tables(df, ticker):
    if df.empty or len(df) < 200:
        return None

    # إسقاط الصفوف التي تحتوي على قيم NaN في سعر الإغلاق (مثل الأيام غير المكتملة)
    df = df.dropna(subset=['close']).reset_index(drop=True)
    if len(df) < 200:
        return None

    close_price = round(df['close'].iloc[-1], 2)
    prev_close = df['close'].iloc[-2]
    
    # الجداول الخمسة
    t1_ma = {'الرمز': ticker, 'السعر': close_price, 'قيمة المتوسط': close_price, 'الإيجابي': 0, 'السلبي': 0, 'تفاصيل': 'تقرير الشركة'}
    t2_ind = {'الرمز': ticker, 'السعر': close_price, 'الإيجابي': 0, 'السلبي': 0, 'تفاصيل': 'تقرير الشركة'}
    t3_sig = {'الرمز': ticker, 'السعر': close_price, 'الإيجابي': 0, 'السلبي': 0, 'تفاصيل': 'تقرير الشركة'}
    t4_sat = {'الرمز': ticker, 'السعر': close_price, 'الإيجابي': 0, 'السلبي': 0, 'تفاصيل': 'تقرير الشركة'}
    t5_ichi = {'الرمز': ticker, 'السعر': close_price, 'الإيجابي': 0, 'السلبي': 0, 'تفاصيل': 'تقرير الشركة'}

    # ================= 1. المتوسطات =================
    for p in [3, 5, 10, 20, 50, 100, 200]:
        col_name = f'المتوسط {p}'
        df[f'MA_{p}'] = df.ta.sma(length=p)
        ma_val = df[f'MA_{p}'].iloc[-1]
        t1_ma[col_name] = round(ma_val, 2) if pd.notna(ma_val) else 0
        
        if pd.notna(ma_val) and ma_val != 0:
            dev = ((close_price - ma_val) / ma_val) * 100
            if dev > 0: t1_ma['الإيجابي'] += 1
            elif dev < 0: t1_ma['السلبي'] += 1

    # ================= 2. حالة المؤشرات =================
    df.ta.macd(append=True)
    df.ta.aroon(append=True)
    df.ta.psar(append=True)
    df.ta.cmf(append=True)
    df.ta.ppo(append=True)
    df.ta.roc(append=True)
    df.ta.eom(append=True)
    
    latest = df.iloc[-1]
    
    # Parabolic SAR
    psar_l = latest.get("PSARl_0.02_0.2", None)
    psar_s = latest.get("PSARs_0.02_0.2", None)
    if pd.notna(psar_l):
        psar_val = psar_l
        is_psar_bull = True
    elif pd.notna(psar_s):
        psar_val = psar_s
        is_psar_bull = False
    else:
        psar_val = close_price
        is_psar_bull = close_price > psar_val

    t2_ind['Aroon Up'] = int(latest.get('AROONU_14', 0)) if pd.notna(latest.get('AROONU_14')) else 0
    t2_ind['Aroon Down'] = int(latest.get('AROOND_14', 0)) if pd.notna(latest.get('AROOND_14')) else 0
    t2_ind['Aroon Oscillat'] = int(latest.get('AROONOSC_14', 0)) if pd.notna(latest.get('AROONOSC_14')) else 0
    t2_ind['MACD'] = round(latest.get('MACD_12_26_9', 0), 3) if pd.notna(latest.get('MACD_12_26_9')) else 0
    t2_ind['MACD Signal'] = round(latest.get('MACDs_12_26_9', 0), 3) if pd.notna(latest.get('MACDs_12_26_9')) else 0
    t2_ind['MACD Histogr'] = round(latest.get('MACDh_12_26_9', 0), 3) if pd.notna(latest.get('MACDh_12_26_9')) else 0
    t2_ind['Parabolic SA'] = 'إيجابي' if is_psar_bull else 'سلبي'
    t2_ind['CMF'] = round(latest.get('CMF_20', 0), 3) if pd.notna(latest.get('CMF_20')) else 0
    t2_ind['PPO'] = round(latest.get('PPO_12_26_9', 0), 3) if pd.notna(latest.get('PPO_12_26_9')) else 0
    t2_ind['ROC'] = round(latest.get('ROC_10', 0), 3) if pd.notna(latest.get('ROC_10')) else 0
    
    eom_col = [c for c in df.columns if c.startswith('EOM_')][0] if any(c.startswith('EOM_') for c in df.columns) else None
    t2_ind['EOM'] = round(latest.get(eom_col, 0), 3) if eom_col and pd.notna(latest.get(eom_col)) else 0

    # العدادات لـ T2 (11 مؤشراً)
    if t2_ind['Aroon Up'] > t2_ind['Aroon Down']: t2_ind['الإيجابي'] += 1
    elif t2_ind['Aroon Down'] > t2_ind['Aroon Up']: t2_ind['السلبي'] += 1

    if t2_ind['Aroon Oscillat'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['Aroon Oscillat'] < 0: t2_ind['السلبي'] += 1

    if t2_ind['MACD'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['MACD'] < 0: t2_ind['السلبي'] += 1

    if t2_ind['MACD Signal'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['MACD Signal'] < 0: t2_ind['السلبي'] += 1

    if t2_ind['MACD Histogr'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['MACD Histogr'] < 0: t2_ind['السلبي'] += 1

    if is_psar_bull: t2_ind['الإيجابي'] += 1
    else: t2_ind['السلبي'] += 1

    if t2_ind['CMF'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['CMF'] < 0: t2_ind['السلبي'] += 1

    if t2_ind['PPO'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['PPO'] < 0: t2_ind['السلبي'] += 1

    if t2_ind['ROC'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['ROC'] < 0: t2_ind['السلبي'] += 1

    if t2_ind['EOM'] > 0: t2_ind['الإيجابي'] += 1
    elif t2_ind['EOM'] < 0: t2_ind['السلبي'] += 1

    # ================= 3. الإشارات الفنية =================
    prev = df.iloc[-2]
    df.ta.adx(append=True)
    df.ta.stoch(append=True)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    ma20_curr = latest.get('MA_20', close_price)
    ma20_prev = prev.get('MA_20', prev_close)
    ma5_curr = latest.get('MA_5', close_price)
    ma5_prev = prev.get('MA_5', prev_close)
    
    # اختراق متوسط 1
    if close_price > ma20_curr and prev_close <= ma20_prev:
        t3_sig['اختراق متوسط 1'] = 'إيجابي'
    elif close_price < ma20_curr and prev_close >= ma20_prev:
        t3_sig['اختراق متوسط 1'] = 'سلبي'
    else:
        t3_sig['اختراق متوسط 1'] = '-'

    # تقاطع متوسطات
    if ma5_curr > ma20_curr and ma5_prev <= ma20_prev:
        t3_sig['تقاطع متوسطات'] = 'إيجابي'
    elif ma5_curr < ma20_curr and ma5_prev >= ma20_prev:
        t3_sig['تقاطع متوسطات'] = 'سلبي'
    else:
        t3_sig['تقاطع متوسطات'] = '-'

    # اختراق MACD
    macd_curr = latest.get('MACD_12_26_9', 0)
    macd_prev = prev.get('MACD_12_26_9', 0)
    if macd_curr > 0 and macd_prev <= 0:
        t3_sig['اختراق MACD'] = 'إيجابي'
    elif macd_curr < 0 and macd_prev >= 0:
        t3_sig['اختراق MACD'] = 'سلبي'
    else:
        t3_sig['اختراق MACD'] = '-'

    # تقاطع MACD
    macds_curr = latest.get('MACDs_12_26_9', 0)
    macds_prev = prev.get('MACDs_12_26_9', 0)
    if macd_curr > macds_curr and macd_prev <= macds_prev:
        t3_sig['تقاطع MACD'] = 'إيجابي'
    elif macd_curr < macds_curr and macd_prev >= macds_prev:
        t3_sig['تقاطع MACD'] = 'سلبي'
    else:
        t3_sig['تقاطع MACD'] = '-'

    # تقاطع Stochas
    stochk_curr = latest.get('STOCHk_14_3_3', 50)
    stochd_curr = latest.get('STOCHd_14_3_3', 50)
    stochk_prev = prev.get('STOCHk_14_3_3', 50)
    stochd_prev = prev.get('STOCHd_14_3_3', 50)
    if stochk_curr > stochd_curr and stochk_prev <= stochd_prev:
        t3_sig['تقاطع Stochas'] = 'إيجابي'
    elif stochk_curr < stochd_curr and stochk_prev >= stochd_prev:
        t3_sig['تقاطع Stochas'] = 'سلبي'
    else:
        t3_sig['تقاطع Stochas'] = '-'

    # تقاطع Aroon
    aroon_u_curr = latest.get('AROONU_14', 0)
    aroon_d_curr = latest.get('AROOND_14', 0)
    aroon_u_prev = prev.get('AROONU_14', 0)
    aroon_d_prev = prev.get('AROOND_14', 0)
    if aroon_u_curr > aroon_d_curr and aroon_u_prev <= aroon_d_prev:
        t3_sig['تقاطع Aroon'] = 'إيجابي'
    elif aroon_u_curr < aroon_d_curr and aroon_u_prev >= aroon_d_prev:
        t3_sig['تقاطع Aroon'] = 'سلبي'
    else:
        t3_sig['تقاطع Aroon'] = '-'

    # تقاطع ADX
    dmp_curr = latest.get('DMP_14', 0)
    dmn_curr = latest.get('DMN_14', 0)
    dmp_prev = prev.get('DMP_14', 0)
    dmn_prev = prev.get('DMN_14', 0)
    if dmp_curr > dmn_curr and dmp_prev <= dmn_prev:
        t3_sig['تقاطع ADX'] = 'إيجابي'
    elif dmp_curr < dmn_curr and dmp_prev >= dmn_prev:
        t3_sig['تقاطع ADX'] = 'سلبي'
    else:
        t3_sig['تقاطع ADX'] = '-'

    # Ichimoku indicators
    ichi_df, _ = df.ta.ichimoku()
    if ichi_df is not None and not ichi_df.empty:
        tenkan_curr = ichi_df['ITS_9'].iloc[-1]
        kijun_curr = ichi_df['IKS_26'].iloc[-1]
        senkou_a_curr = ichi_df['ISA_9'].iloc[-1]
        senkou_b_curr = ichi_df['ISB_26'].iloc[-1]

        tenkan_prev = ichi_df['ITS_9'].iloc[-2]
        kijun_prev = ichi_df['IKS_26'].iloc[-2]
        senkou_a_prev = ichi_df['ISA_9'].iloc[-2]
        senkou_b_prev = ichi_df['ISB_26'].iloc[-2]

        cloud_max_curr = max(senkou_a_curr, senkou_b_curr)
        cloud_min_curr = min(senkou_a_curr, senkou_b_curr)
        cloud_max_prev = max(senkou_a_prev, senkou_b_prev)
        cloud_min_prev = min(senkou_a_prev, senkou_b_prev)

        # غيمة جديدة
        if senkou_a_curr > senkou_b_curr and senkou_a_prev <= senkou_b_prev:
            t3_sig['غيمة جديدة'] = 'إيجابي'
        elif senkou_a_curr < senkou_b_curr and senkou_a_prev >= senkou_b_prev:
            t3_sig['غيمة جديدة'] = 'سلبي'
        else:
            t3_sig['غيمة جديدة'] = '-'

        # اختراق الغيمة
        if close_price > cloud_max_curr and prev_close <= cloud_max_prev:
            t3_sig['اختراق الغيمة'] = 'إيجابي'
        elif close_price < cloud_min_curr and prev_close >= cloud_min_prev:
            t3_sig['اختراق الغيمة'] = 'سلبي'
        else:
            t3_sig['اختراق الغيمة'] = '-'

        # اختراق Kijun
        if close_price > kijun_curr and prev_close <= kijun_prev:
            t3_sig['اختراق Kijun'] = 'إيجابي'
        elif close_price < kijun_curr and prev_close >= kijun_prev:
            t3_sig['اختراق Kijun'] = 'سلبي'
        else:
            t3_sig['اختراق Kijun'] = '-'

        # تقاطع Tenken
        if tenkan_curr > kijun_curr and tenkan_prev <= kijun_prev:
            t3_sig['تقاطع Tenken'] = 'إيجابي'
        elif tenkan_curr < kijun_curr and tenkan_prev >= kijun_prev:
            t3_sig['تقاطع Tenken'] = 'سلبي'
        else:
            t3_sig['تقاطع Tenken'] = '-'
    else:
        t3_sig.update({'غيمة جديدة': '-', 'اختراق الغيمة': '-', 'اختراق Kijun': '-', 'تقاطع Tenken': '-'})

    # انعكاس Parabl
    prev_psar_l = prev.get("PSARl_0.02_0.2", None)
    prev_psar_s = prev.get("PSARs_0.02_0.2", None)
    was_psar_bull = pd.notna(prev_psar_l)
    if is_psar_bull and not was_psar_bull:
        t3_sig['انعكاس Parabl'] = 'إيجابي'
    elif not is_psar_bull and was_psar_bull:
        t3_sig['انعكاس Parabl'] = 'سلبي'
    else:
        t3_sig['انعكاس Parabl'] = '-'

    # فجوة سعرية
    if latest['open'] > prev['high']:
        t3_sig['فجوة سعرية'] = 'إيجابي'
    elif latest['open'] < prev['low']:
        t3_sig['فجوة سعرية'] = 'سلبي'
    else:
        t3_sig['فجوة سعرية'] = '-'

    # حساب العدادات لـ T3
    for k in ['اختراق متوسط 1', 'تقاطع متوسطات', 'اختراق MACD', 'تقاطع MACD', 'تقاطع Stochas', 
              'تقاطع Aroon', 'تقاطع ADX', 'غيمة جديدة', 'اختراق الغيمة', 'اختراق Kijun', 
              'تقاطع Tenken', 'انعكاس Parabl', 'فجوة سعرية']:
        if t3_sig.get(k) == 'إيجابي': t3_sig['الإيجابي'] += 1
        elif t3_sig.get(k) == 'سلبي': t3_sig['السلبي'] += 1

    # ================= 4. تشبع البيع والشراء =================
    df.ta.rsi(append=True)
    df.ta.stochrsi(append=True)
    df.ta.cci(append=True)
    df.ta.mfi(append=True)
    df.ta.willr(append=True)
    latest = df.iloc[-1]

    def check_sat(val, over_s, over_b):
        if pd.isna(val): return '-'
        if val <= over_s: return 'تشبع بيع'
        if val >= over_b: return 'تشبع شراء'
        return '-'

    t4_sat['RSI'] = check_sat(latest.get('RSI_14', 50), 30, 70)
    t4_sat['Stochastic D'] = check_sat(latest.get('STOCHd_14_3_3', 50), 20, 80)
    t4_sat['Stochastic K'] = check_sat(latest.get('STOCHk_14_3_3', 50), 20, 80)
    t4_sat['StochRSI'] = check_sat(latest.get('STOCHRSIk_14_14_3_3', 0.5) * 100, 20, 80)
    t4_sat['CCI'] = check_sat(latest.get('CCI_14_0.015', 0), -100, 100)
    t4_sat['MFI'] = check_sat(latest.get('MFI_14', 50), 20, 80)
    t4_sat['W%R'] = check_sat(latest.get('WILLR_14', -50), -80, -20)

    for k in ['RSI', 'Stochastic D', 'Stochastic K', 'StochRSI', 'CCI', 'MFI', 'W%R']:
        if t4_sat[k] == 'تشبع بيع': t4_sat['الإيجابي'] += 1
        elif t4_sat[k] == 'تشبع شراء': t4_sat['السلبي'] += 1

    # ================= 5. ايشيموكو =================
    if ichi_df is not None and not ichi_df.empty:
        tenkan = ichi_df['ITS_9'].iloc[-1]
        kijun = ichi_df['IKS_26'].iloc[-1]
        senkou_a = ichi_df['ISA_9'].iloc[-1]
        senkou_b = ichi_df['ISB_26'].iloc[-1]
        
        cloud_max = max(senkou_a, senkou_b)
        cloud_min = min(senkou_a, senkou_b)
        
        if close_price > cloud_max:
            t5_ichi['القيمة'] = 'أعلى من القيمة'
            t5_ichi['السعر مع القيمة'] = 'إيجابي'
            t5_ichi['الإيجابي'] += 2
        elif close_price < cloud_min:
            t5_ichi['القيمة'] = 'أدنى من القيمة'
            t5_ichi['السعر مع القيمة'] = 'سلبي'
            t5_ichi['السلبي'] += 2
        else:
            t5_ichi['القيمة'] = '-'
            t5_ichi['السعر مع القيمة'] = '-'

        if close_price > kijun:
            t5_ichi['Kijun'] = 'إيجابي'
            t5_ichi['الإيجابي'] += 1
        elif close_price < kijun:
            t5_ichi['Kijun'] = 'سلبي'
            t5_ichi['السلبي'] += 1
        else:
            t5_ichi['Kijun'] = '-'
            
        if tenkan > kijun:
            t5_ichi['Tenken Sen'] = 'إيجابي'
            t5_ichi['الإيجابي'] += 1
        elif tenkan < kijun:
            t5_ichi['Tenken Sen'] = 'سلبي'
            t5_ichi['السلبي'] += 1
        else:
            t5_ichi['Tenken Sen'] = '-'
    else:
        t5_ichi.update({'القيمة': '-', 'السعر مع القيمة': '-', 'Kijun': '-', 'Tenken Sen': '-'})

    return t1_ma, t2_ind, t3_sig, t4_sat, t5_ichi
