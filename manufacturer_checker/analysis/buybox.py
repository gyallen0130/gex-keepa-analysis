"""v4.4由来の履歴時間積分。率は観測期間を分母とする0〜100値。"""
import time
KEEPA_OFFSET = 21564000

def now_keepa_minutes():
    return int(time.time() // 60) - KEEPA_OFFSET

def parse_buybox_history(history):
    if not history:
        return []
    events = []
    for i in range(0, len(history) - 1, 2):
        try:
            events.append((int(history[i]), str(history[i + 1])))
        except Exception:
            pass
    return sorted(events, key=lambda x: x[0])

def calculate_bb_share(history, days, amazon_ids, *, now=None):
    if days <= 0:
        raise ValueError("daysは正数")
    events = parse_buybox_history(history)
    empty = {
        "amazon_pct": None,
        "other_pct": None,
        "suppressed_pct": None,
        "unknown_pct": None,
        "other_days": 0.0,
        "coverage_pct": 0.0,
    }
    if not events:
        return empty

    now_k = now_keepa_minutes() if now is None else now
    window_start = now_k - days * 24 * 60
    current_seller = None
    observation_start = None

    for ts, seller in events:
        if ts <= window_start:
            current_seller = seller
            observation_start = window_start
        else:
            break

    if current_seller is None:
        future = [e for e in events if window_start <= e[0] <= now_k]
        if not future:
            return empty
        observation_start, current_seller = future[0]

    window_events = [
        (ts, seller) for ts, seller in events
        if observation_start < ts <= now_k
    ]
    totals = {"amazon": 0, "other": 0, "suppressed": 0, "unknown": 0}

    def category(seller):
        if seller in amazon_ids:
            return "amazon"
        if seller == "-1":
            return "suppressed"
        if seller in ("-2", "", "None", "nan"):
            return "unknown"
        return "other"

    previous = observation_start
    seller = current_seller
    for ts, new_seller in window_events:
        totals[category(seller)] += max(0, ts - previous)
        previous, seller = ts, new_seller
    totals[category(seller)] += max(0, now_k - previous)

    observed = sum(totals.values())
    if observed <= 0:
        return empty
    return {
        "amazon_pct": round(totals["amazon"] / observed * 100, 1),
        "other_pct": round(totals["other"] / observed * 100, 1),
        "suppressed_pct": round(totals["suppressed"] / observed * 100, 1),
        "unknown_pct": round(totals["unknown"] / observed * 100, 1),
        "other_days": round(totals["other"] / 1440, 1),
        "coverage_pct": round(min(100, observed / (days * 1440) * 100), 1),
    }
