def get_chaos_persona_instructions(chaos_level: int) -> str:
    if chaos_level <= 2:
        return "CHAOS SCALE 0-2 (STRICT PROTOCOL): Leaders and ministers are polite, calculating, aristocratic."
    elif chaos_level <= 5:
        return "CHAOS SCALE 3-5 (TENSION): Leaders are blunt, pushy, making bold unilateral demands."
    elif chaos_level <= 8:
        return "CHAOS SCALE 6-8 (HOSTILITY & PANIC): Leaders issue aggressive ultimatums, sarcastic remarks, and erratic threats."
    else:
        return "CHAOS SCALE 9-10 (UNHINGED MADNESS): Leaders dispatch wild ALL-CAPS ultimatums, demanding total submission or threatening absurd cosmic wars. Ministers lose all filter."

def get_alt_history_directive(is_alt_history: bool, world_ctx: str) -> str:
    if not is_alt_history and not world_ctx:
        return ""
    return f"""
=== CANONICAL SCENARIO LORE (PRIORITY OVER REAL HISTORY) ===
{world_ctx}
DIRECTIVE: This is an ALTERNATE HISTORY / FICTIONAL LORE scenario. Strictly adhere to provided lore!
============================================================
"""