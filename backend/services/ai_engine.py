"""
ZTII AI Rule Engine

Version 1.0
Rule-based industrial health assessment.
"""


def analyze_device(temperature: float, vibration: float):
    """
    Analyze machine condition based on sensor values.

    Returns:
        health
        risk
        recommendation
    """

    # ----------------------------
    # Critical
    # ----------------------------
    if temperature >= 35 and vibration >= 2:

        return {
            "health": "🔴 Critical",
            "risk": "High",
            "recommendation": (
                "Immediate inspection required. "
                "Check cooling system and motor bearings."
            )
        }

    # ----------------------------
    # High Temperature
    # ----------------------------
    elif temperature >= 35:

        return {
            "health": "🟡 Warning",
            "risk": "Medium",
            "recommendation": (
                "Inspect cooling system."
            )
        }

    # ----------------------------
    # High Vibration
    # ----------------------------
    elif vibration >= 2:

        return {
            "health": "🟠 Warning",
            "risk": "Medium",
            "recommendation": (
                "Inspect bearings and shaft alignment."
            )
        }

    # ----------------------------
    # Normal
    # ----------------------------
    else:

        return {
            "health": "🟢 Normal",
            "risk": "Low",
            "recommendation": (
                "No maintenance required."
            )
        }