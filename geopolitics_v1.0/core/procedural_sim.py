import random

def run_procedural_background_noise(countries: dict, player_country: str, current_turn: int):
    """
    Математический 'белый шум' для спящих и минорных стран (0 токенов ИИ).
    Полная защита от любых нераспарсенных типов данных.
    """
    if not isinstance(countries, dict):
        return

    for c_name, c_data in countries.items():
        if c_name == player_country or not isinstance(c_data, dict):
            continue
        
        # Миноры и спящие страны
        if not c_data.get("is_great_power", False) or c_data.get("status") == "Спящая":
            stats = c_data.setdefault("stats", {})
            if isinstance(stats, dict):
                cur_stab = stats.get("stability", 50)
                if isinstance(cur_stab, (int, float)):
                    if cur_stab < 50:
                        stats["stability"] = min(100, int(cur_stab) + random.choice([0, 1]))
                    elif cur_stab > 60:
                        stats["stability"] = max(0, int(cur_stab) - random.choice([0, 1]))
                
            # Фоновое пополнение базовых складов
            mil = c_data.get("military")
            if isinstance(mil, dict):
                inf_list = mil.get("infantry", [])
                if isinstance(inf_list, list):
                    for eq in inf_list:
                        if isinstance(eq, dict) and eq.get("production", False):
                            cur_c = eq.get("count", 1000)
                            if isinstance(cur_c, (int, float)):
                                eq["count"] = int(cur_c) + random.randint(10, 80)