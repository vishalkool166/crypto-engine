from datetime import datetime, timezone


def get_session(current_time=None) -> dict:
    now        = current_time if current_time else datetime.now(timezone.utc)
    hour       = now.hour + now.minute / 60
    weekday    = now.weekday()
    is_weekend = weekday >= 5

    london  = 8  <= hour < 16
    ny      = 13 <= hour < 21
    asia    = 0  <= hour < 8

    if london and ny:
        s = {
            "name":      "London/NY Overlap",
            "quality":   "BEST",
            "score":     9,
            "tradeable": True,
        }
    elif ny:
        s = {
            "name":      "New York",
            "quality":   "GOOD",
            "score":     7,
            "tradeable": True,
        }
    elif london:
        s = {
            "name":      "London",
            "quality":   "GOOD",
            "score":     7,
            "tradeable": True,
        }
    elif asia:
        s = {
            "name":      "Asia",
            "quality":   "LOW",
            "score":     3,
            "tradeable": True,
        }
    else:
        s = {
            "name":      "Off Hours",
            "quality":   "LOW",
            "score":     2,
            "tradeable": True,
        }

    if is_weekend:
        s["quality"]  = "LOW"
        s["score"]    = max(2, s["score"] - 3)
        s["weekend"]  = True
    else:
        s["weekend"]  = False

    return s