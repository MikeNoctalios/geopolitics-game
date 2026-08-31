def extract_year(date_str: str) -> int:
    for y in range(1800, 2100):
        if str(y) in str(date_str):
            return y
    return 1935