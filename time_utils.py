import pytz
from datetime import datetime

TZ = pytz.timezone('Asia/Riyadh')


def now_riyadh():
    return datetime.now(TZ)


def is_market_day(dt=None):
    dt = dt or now_riyadh()
    return dt.weekday() in [6, 0, 1, 2, 3]


def can_fetch_1h(dt=None):
    dt = dt or now_riyadh()
    if not is_market_day(dt):
        return False, 'السوق مغلق (عطلة نهاية الأسبوع)'
    if dt.minute < 15:
        remaining = 15 - dt.minute
        return False, f'ينتظر {remaining} دقيقة لتحديث بيانات الساعة'
    return True, ''


def can_fetch_1d(dt=None):
    dt = dt or now_riyadh()
    if not is_market_day(dt):
        return False, 'السوق مغلق (عطلة نهاية الأسبوع)'
    if dt.hour < 16:
        return False, f'ينتظر حتى الساعة 4م (الآن {dt.hour:02d}:{dt.minute:02d})'
    return True, ''
