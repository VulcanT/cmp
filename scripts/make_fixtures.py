"""Generate deterministic fixtures for one app with six keywords covering every rule path.

Re-run after changing the fixture story: `python scripts/make_fixtures.py`.
Shapes mirror the Apple Ads Platform API docs; the AppsFlyer shape is an assumption to be
replaced by a captured real response (see src/cmp/ingest/appsflyer.py).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
AS_OF = date(2026, 10, 15)  # run date; cohort days are D-14..D-1
APP_ID = "id1234567890"
AD_ACCOUNT = 123456789
CAMPAIGN = 444555666
AD_GROUP = 555666777
CAMPAIGN_NAME, AD_GROUP_NAME = "Camp A - US - Exact", "AG1"

# id, text, bid, status, spend/day, installs/day, revenue_d7/day
KEYWORDS = [
    (1001, "photo editor", "1.00", "ENABLED", "2.00", 4, "20.00"),  # winner → +15%
    (1002, "collage maker", "1.00", "ENABLED", "2.00", 2, "0.20"),  # loser → -20%
    (1003, "free app", "0.50", "ENABLED", "3.00", 0, "0.00"),  # dead → PAUSED
    (1004, "Photo Editor Pro", "1.00", "ENABLED", "1.00", 1, "3.00"),  # uppercase → no AF cost
    (1005, "wallpaper", "2.00", "ENABLED", "2.00", 4, "20.00"),  # winner at bid cap → dropped
    (1006, "thin keyword", "0.80", "ENABLED", "0.30", 0, "0.50"),  # too little data
]


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    write(
        ROOT / "app.json",
        {
            "app_id": APP_ID,
            "ad_account_id": AD_ACCOUNT,
            "as_of": AS_OF.isoformat(),
            "campaign_names": {str(CAMPAIGN): CAMPAIGN_NAME},
        },
    )
    write(
        ROOT / "apple" / f"adgroups_{CAMPAIGN}.json",
        {
            "result": [
                {
                    "id": AD_GROUP,
                    "campaignId": CAMPAIGN,
                    "name": AD_GROUP_NAME,
                    "status": "ENABLED",
                    "defaultBid": {"amount": "1.00", "currency": "USD"},
                }
            ],
            "pagination": {"offset": 0, "pageSize": 500, "totalCount": 1},
        },
    )
    write(
        ROOT / "apple" / f"keywords_{CAMPAIGN}.json",
        {
            "result": [
                {
                    "id": kid,
                    "adAccountId": AD_ACCOUNT,
                    "campaignId": CAMPAIGN,
                    "adGroupId": AD_GROUP,
                    "text": text,
                    "matchType": "EXACT",
                    "bid": {"amount": bid, "currency": "USD"},
                    "status": status,
                    "displayStatus": "RUNNING",
                    "deleted": False,
                }
                for kid, text, bid, status, *_ in KEYWORDS
            ],
            "pagination": {"offset": 0, "pageSize": 500, "totalCount": 6},
        },
    )

    days = [AS_OF - timedelta(days=i) for i in range(14, 0, -1)]
    rows = []
    for kid, text, _bid, status, spend, installs, _rev in KEYWORDS:
        rows.append(
            {
                "metadata": {
                    "id": kid,
                    "text": text,
                    "matchType": "EXACT",
                    "adAccountId": AD_ACCOUNT,
                    "campaignId": CAMPAIGN,
                    "adGroupId": AD_GROUP,
                    "status": status,
                    "deleted": False,
                },
                "totalMetrics": {
                    "localSpend": {"amount": f"{float(spend) * 14:.2f}", "currency": "USD"}
                },
                "granularMetrics": [
                    {
                        "date": d.isoformat(),
                        "localSpend": {"amount": spend, "currency": "USD"},
                        "impressions": 100,
                        "taps": 10,
                        "tapInstalls": installs,
                        "totalInstalls": installs,
                    }
                    for d in days
                ],
            }
        )
    write(
        ROOT / "apple" / f"keyword_report_{CAMPAIGN}.json",
        {
            "result": {"rows": rows},
            "pagination": {"totalCount": len(rows), "offset": 0, "pageSize": 5000},
        },
    )

    for d in days:
        results = []
        for _kid, text, _bid, _status, spend, installs, rev in KEYWORDS:
            if text != text.lower():
                continue  # AppsFlyer drops cost for uppercase keywords; row absent entirely here
            results.append(
                {
                    "c": CAMPAIGN_NAME,
                    "af_adset": AD_GROUP_NAME,
                    "af_keywords": text,
                    "users": installs,
                    "cost": spend,
                    "ecpi": None,
                    "revenue": {"0": f"{float(rev) * 0.4:.2f}", "7": rev},
                }
            )
        write(ROOT / "appsflyer" / f"{APP_ID}_revenue_{d.isoformat()}.json", {"results": results})
    print(f"fixtures written under {ROOT}")


if __name__ == "__main__":
    main()
