import csv
import json
import urllib.request

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_URL  = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"


def download_text(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_pipe_delimited(text: str):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("File Creation Time:")]
    reader = csv.DictReader(lines, delimiter="|")
    return list(reader)


def is_common_stock(name: str) -> bool:
    return bool(name) and ("common stock" in name.lower())


def is_etf_row(row: dict) -> bool:
    # NASDAQ file: explicit ETF flag exists
    if "ETF" in row and row.get("ETF") == "Y":
        return True

    # OTHER file (NYSE etc): identify via Security Name text
    name = row.get("Security Name", "")
    if not name:
        return False
    name_l = name.lower()
    return (" etf" in name_l) or ("exchange traded fund" in name_l) or (name_l.endswith("etf"))


def clean_security_name(name: str) -> str:
    if not name:
        return ""
    # Remove common suffixes for nicer display
    out = name
    out = out.replace("- Common Stock", "")
    out = out.replace(" Common Stock", "")
    out = out.strip()
    return out


def main():
    nasdaq_text = download_text(NASDAQ_URL)
    other_text  = download_text(OTHER_URL)

    nasdaq_rows = parse_pipe_delimited(nasdaq_text)
    other_rows  = parse_pipe_delimited(other_text)

    # ------------------------
    # NASDAQ – common stocks + ETFs
    # ------------------------
    nasdaq_securities = [
        {
            "ticker": r["Symbol"].strip(),
            "name": clean_security_name(r.get("Security Name", "")),
            "exchange": "NASDAQ",
            "asset_type": "ETF" if is_etf_row(r) else "STOCK",
        }
        for r in nasdaq_rows
        if r.get("Test Issue") == "N"
        and (is_common_stock(r.get("Security Name", "")) or is_etf_row(r))
    ]

    # ------------------------
    # NYSE – common stocks + ETFs
    # ------------------------
    nyse_securities = [
        {
            "ticker": r["ACT Symbol"].strip(),
            "name": clean_security_name(r.get("Security Name", "")),
            "exchange": "NYSE",
            "asset_type": "ETF" if is_etf_row(r) else "STOCK",
        }
        for r in other_rows
        if r.get("Test Issue") == "N"
        and r.get("Exchange") == "N"
        and (is_common_stock(r.get("Security Name", "")) or is_etf_row(r))
    ]

    with open("nasdaq.json", "w", encoding="utf-8") as f:
        json.dump(nasdaq_securities, f, indent=2)

    with open("nyse.json", "w", encoding="utf-8") as f:
        json.dump(nyse_securities, f, indent=2)

    print(f"NASDAQ stocks+ETFs: {len(nasdaq_securities)}")
    print(f"NYSE stocks+ETFs:   {len(nyse_securities)}")


if __name__ == "__main__":
    main()
