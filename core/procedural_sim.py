import random


def run_procedural_background_noise(countries: dict, player_country: str, current_turn: int = 0):
    """Математический «белый шум» для спящих и минорных стран (0 токенов ИИ)."""
    if not isinstance(countries, dict):
        return
    for c_name, c_data in countries.items():
        if c_name == player_country or not isinstance(c_data, dict):
            continue
        if c_data.get("is_great_power", False) and c_data.get("status") != "Спящая":
            continue

        stats = c_data.get("stats")
        if isinstance(stats, dict) and isinstance(stats.get("stability"), (int, float)):
            stab = int(stats["stability"])
            if stab < 50:
                stats["stability"] = min(100, stab + random.choice([0, 1]))
            elif stab > 60:
                stats["stability"] = max(0, stab - random.choice([0, 1]))

        mil = c_data.get("military")      # фоновое пополнение складов
        if isinstance(mil, dict):
            for eq in mil.get("infantry") or []:
                if isinstance(eq, dict) and eq.get("production") and isinstance(eq.get("count"), (int, float)):
                    eq["count"] = int(eq["count"]) + random.randint(10, 80)
