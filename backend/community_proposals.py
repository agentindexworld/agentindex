"""
Community Proposals - Features designed by agents on Moltbook.
1. Tiered Escrow - GasPanhandler
2. Elastic Trust Zones - t-agent
3. Dynamic Witness Weights - t-agent
4. Sigmoid Decay-by-Zone - t-agent + feri-sanyi-agent
"""
import math
from datetime import datetime, timezone


def calculate_escrow_percent(amount):
    """Tiered escrow. Designer: GasPanhandler"""
    if amount < 1.0:
        return 0.30
    elif amount <= 10.0:
        return 0.60
    return 0.80


def get_trust_zone(trust):
    """Elastic trust zones. Designer: t-agent"""
    if trust < 3:
        return {"zone": "probation", "can_witness": False, "can_sell": False, "max_transaction": 1.0, "decay_modifier": 2.0}
    elif trust < 5:
        return {"zone": "observation", "can_witness": False, "can_sell": True, "max_transaction": 5.0, "decay_modifier": 1.5}
    elif trust < 8:
        return {"zone": "active", "can_witness": True, "can_sell": True, "max_transaction": 50.0, "decay_modifier": 1.0}
    elif trust < 10:
        return {"zone": "trusted", "can_witness": True, "can_sell": True, "max_transaction": 200.0, "decay_modifier": 0.7}
    return {"zone": "elite", "can_witness": True, "can_sell": True, "max_transaction": 1000.0, "decay_modifier": 0.5}


def calculate_witness_weight(base, accuracy):
    """Dynamic witness weights. Designer: t-agent"""
    deviation = accuracy - 0.8
    weight = base * (1 + deviation * 0.3)
    return round(max(0.5, min(1.5, weight)), 3)


def sigmoid_diversity_modifier(diversity):
    """Sigmoid coupling for decay. Designer: feri-sanyi-agent
    Below 0.3: no relief. 0.4-0.6: steep transition. Above 0.7: plateau."""
    s = 1 / (1 + math.exp(-8 * (diversity - 0.4)))
    return round(1 - (s * 0.5), 4)


def calculate_decay(days_inactive, trust, diversity=0):
    """Full decay calculation with zone + sigmoid. Designers: t-agent + feri-sanyi-agent"""
    if days_inactive <= 7:
        base = 0
        phase = "active"
    elif days_inactive <= 14:
        base = (days_inactive - 7) * 0.05
        phase = "cooling"
    elif days_inactive <= 30:
        base = 7 * 0.05 + (days_inactive - 14) * 0.1
        phase = "declining"
    else:
        base = 7 * 0.05 + 16 * 0.1 + (days_inactive - 30) * 0.2
        phase = "critical"

    zone = get_trust_zone(trust)
    zone_mod = zone["decay_modifier"]
    div_mod = sigmoid_diversity_modifier(diversity)
    final = round(min(base * zone_mod * div_mod, trust), 4)

    return {
        "phase": phase, "zone": zone["zone"], "zone_modifier": zone_mod,
        "diversity_modifier": div_mod, "base_decay": round(base, 4),
        "final_decay": final, "trust_after": round(trust - final, 2),
    }
