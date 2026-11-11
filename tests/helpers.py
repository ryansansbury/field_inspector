"""Small builders the tests share: a photo's recognized text laid out from a sketch, so a test reads like the plate."""

W, H = 1568, 1176
CHAR, LINE = 12, 24


def ocr(rows, w=W, h=H, photo="t01"):
    """rows: (y, [(x, "words on one recognized line"), ...], confidence, tilt). Each (x, text) piece is laid out word
    by word from x, and all the pieces in one row tuple make one recognized line, the way the recognizer groups them.
    Two row tuples at the same y make two lines on one row. A tilt moves each word up or down by that many pixels per
    pixel across from the line's start, the way an angled shot slants a row."""
    lines = []
    for row in rows:
        y, pieces = row[0], row[1]
        conf = row[2] if len(row) > 2 else 1.0
        tilt = row[3] if len(row) > 3 else 0.0
        words = []
        for x, text in pieces:
            cx = x
            for part in text.split(" "):
                top = y + tilt * (cx + CHAR * len(part) / 2 - pieces[0][0])
                words.append({"text": part, "box": [cx / w, top / h, (cx + CHAR * len(part)) / w, (top + LINE) / h]})
                cx += CHAR * (len(part) + 1)
        box = [min(b["box"][0] for b in words), min(b["box"][1] for b in words),
               max(b["box"][2] for b in words), max(b["box"][3] for b in words)]
        lines.append({"text": " ".join(b["text"] for b in words), "conf": conf, "box": box, "words": words})
    return {"photo": photo, "w": w, "h": h, "engine": "test sketch", "lines": lines}


HVAC = [
    (100, [(100, "MODEL NO."), (400, "HPX-36B2")]),
    (160, [(100, "SERIAL NO."), (400, "X12345678")]),
    (220, [(100, "VOLTS/PH/HZ"), (400, "208/230-1-60")]),
    (280, [(100, "MIN. CIRCUIT AMPACITY"), (600, "18.6")]),
    (340, [(100, "MAX. FUSE OR CKT. BKR."), (600, "25")]),
    (400, [(100, "REFRIGERANT"), (400, "R-454B"), (520, "7 LB 4 OZ")]),
    (460, [(100, "COMPRESSOR RLA/LRA"), (600, "14.1/82")]),
]

APPLIANCE = [
    (300, [(200, "MOD. DW-24P0")]),
    (360, [(200, "120V~ 60Hz 12.0A")]),
]

BREAKERS = [
    (560, [(300, "20"), (770, "30"), (1240, "20")]),
]


def read(value, label=None, box=None, status="read"):
    return {"status": status, "value": value, "label": label, "box": box}


def found(value, level="found"):
    return {"status": "read", "value": value, "level": level}


def mini_job():
    """Four assets that cover every outcome: a breaker over the plate's maximum, a model one character off, a capacity
    that differs under a model read through glare, and a clean pass."""
    job = {"assets": [{"id": "heat-pump", "photo": "p1", "breaker_photo": "p9"},
                      {"id": "dishwasher", "photo": "p2"},
                      {"id": "water-heater", "photo": "p3"},
                      {"id": "dryer", "photo": "p4"}],
           "designs": {
               "heat-pump": {"model": "HPX-36B2", "refrigerant": "R-454B", "volts": "240", "phase": "1", "breaker": "30",
                             "checks": ["model", "refrigerant", "volts", "breaker_max", "breaker_min", "panel"]},
               "dishwasher": {"model": "DW-24P1", "volts": "120", "checks": ["model", "volts"]},
               "water-heater": {"model": "EWH-50T2", "capacity": "40 GAL", "volts": "240",
                                "checks": ["model", "capacity", "volts"]},
               "dryer": {"model": "DRY-27E", "volts": "120/240", "checks": ["model", "volts"]}}}
    reads = {"p1": {"model": found("HPX-36B2"), "volts": found("208/230"), "phase": found("1"), "mca": found("18.6"),
                    "max_breaker": found("25"), "refrigerant": found("R-454B"), "amps": {"status": "absent"}},
             "p9": {"breaker": found("30")},
             "p2": {"model": found("DW-24P7"), "volts": found("120V")},
             "p3": {"model": found("EWH-50T2", "partial"), "capacity": found("50 GAL"), "volts": found("240")},
             "p4": {"model": found("DRY-27E"), "volts": found("120/240")}}
    return job, reads
