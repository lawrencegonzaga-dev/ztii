"""
ZTII Explainable AI Engine
============================================================

Uses SHAP to explain how:

    - Temperature
    - Vibration

contribute to the calculated machine risk score.

Architecture:

    Current Sensor Data
           ↓
       Risk Model
           ↓
          SHAP
           ↓
    Feature Contributions
           ↓
    Human-readable Explanation
"""


import numpy as np
import shap


# ============================================================
# MODEL BASELINES
# ============================================================

# Normal/reference temperature

TEMP_BASELINE = 40.0
TEMP_SPAN = 40.0


# Normal/reference vibration

VIB_BASELINE = 0.3
VIB_SPAN = 1.7


# ============================================================
# MODEL WEIGHTS
# ============================================================

# Vibration has slightly higher influence because it is an
# important indicator of mechanical problems.

TEMPERATURE_WEIGHT = 0.45
VIBRATION_WEIGHT = 0.55


# ============================================================
# RISK MODEL
# ============================================================

def risk_model(X):
    """
    Calculate the machine risk score used by SHAP.

    Input shape:

        X[:, 0] = Temperature
        X[:, 1] = Vibration

    Output:

        Risk score from approximately 0 to 100.
    """

    X = np.asarray(X, dtype=float)

    # --------------------------------------------------------
    # TEMPERATURE
    # --------------------------------------------------------

    temperature = X[:, 0]

    temp_deviation = np.maximum(
        0.0,
        (temperature - TEMP_BASELINE) / TEMP_SPAN
    )

    # --------------------------------------------------------
    # VIBRATION
    # --------------------------------------------------------

    vibration = X[:, 1]

    vibration_deviation = np.maximum(
        0.0,
        (vibration - VIB_BASELINE) / VIB_SPAN
    )

    # --------------------------------------------------------
    # WEIGHTED RISK
    # --------------------------------------------------------

    risk = (
        vibration_deviation * VIBRATION_WEIGHT
        +
        temp_deviation * TEMPERATURE_WEIGHT
    ) * 100.0

    return risk


# ============================================================
# SHAP BACKGROUND DATA
# ============================================================

BACKGROUND_DATA = np.array(
    [
        [40.0, 0.30],
        [42.0, 0.35],
        [38.0, 0.25],
        [45.0, 0.40],
        [40.0, 0.30],
    ],
    dtype=float
)


# ============================================================
# SHAP EXPLAINER
# ============================================================

explainer = shap.Explainer(
    risk_model,
    BACKGROUND_DATA
)


# ============================================================
# SHAP EXPLANATION
# ============================================================

def explain_prediction(
    temperature: float,
    vibration: float
) -> dict:
    """
    Generate a SHAP explanation for the current machine risk.

    Args:
        temperature:
            Current machine temperature in °C.

        vibration:
            Current machine vibration value.

    Returns:
        Dictionary containing:

            primary_factor
            explanation
            temperature contribution percentage
            vibration contribution percentage
            raw SHAP values
            risk prediction
    """

    # ========================================================
    # VALIDATE INPUTS
    # ========================================================

    try:

        temperature = float(temperature)
        vibration = float(vibration)

    except (TypeError, ValueError) as exc:

        raise ValueError(
            "Temperature and vibration must be numeric values."
        ) from exc

    if not np.isfinite(temperature):

        raise ValueError(
            "Temperature must be a finite number."
        )

    if not np.isfinite(vibration):

        raise ValueError(
            "Vibration must be a finite number."
        )

    # ========================================================
    # CURRENT SAMPLE
    # ========================================================

    sample = np.array(
        [
            [temperature, vibration]
        ],
        dtype=float
    )

    # ========================================================
    # CALCULATE SHAP VALUES
    # ========================================================

    shap_result = explainer(sample)

    values = np.asarray(
        shap_result.values
    )

    # --------------------------------------------------------
    # GET CURRENT SAMPLE CONTRIBUTIONS
    # --------------------------------------------------------

    temperature_shap = float(
        values[0, 0]
    )

    vibration_shap = float(
        values[0, 1]
    )

    # ========================================================
    # ABSOLUTE CONTRIBUTIONS
    # ========================================================

    temperature_abs = abs(
        temperature_shap
    )

    vibration_abs = abs(
        vibration_shap
    )

    total_contribution = (
        temperature_abs
        +
        vibration_abs
    )

    # ========================================================
    # CONTRIBUTION PERCENTAGES
    # ========================================================

    if total_contribution == 0:

        temperature_pct = 50.0
        vibration_pct = 50.0

    else:

        temperature_pct = (
            temperature_abs
            / total_contribution
        ) * 100.0

        vibration_pct = (
            vibration_abs
            / total_contribution
        ) * 100.0

    # ========================================================
    # PRIMARY CONTRIBUTING FACTOR
    # ========================================================

    if temperature_abs >= vibration_abs:

        primary_factor = "Temperature"

    else:

        primary_factor = "Vibration"

    # ========================================================
    # RISK PREDICTION
    # ========================================================

    risk_prediction = float(
        risk_model(sample)[0]
    )

    # ========================================================
    # HUMAN-READABLE EXPLANATION
    # ========================================================

    if primary_factor == "Temperature":

        explanation = (
            f"Temperature is the primary factor affecting "
            f"the predicted machine risk. The current "
            f"temperature is {temperature:.2f} °C and its "
            f"SHAP contribution is "
            f"{temperature_shap:+.2f}."
        )

    else:

        explanation = (
            f"Vibration is the primary factor affecting "
            f"the predicted machine risk. The current "
            f"vibration is {vibration:.2f} and its "
            f"SHAP contribution is "
            f"{vibration_shap:+.2f}."
        )

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {

        "primary_factor": primary_factor,

        "explanation": explanation,

        "temperature": round(
            temperature_pct,
            1
        ),

        "vibration": round(
            vibration_pct,
            1
        ),

        "shap_values": {

            "temperature": round(
                temperature_shap,
                4
            ),

            "vibration": round(
                vibration_shap,
                4
            )
        },

        "risk_prediction": round(
            risk_prediction,
            2
        )
    }


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    test_cases = [

        # Normal
        (40.0, 0.30),

        # Temperature elevated
        (58.0, 0.60),

        # Vibration elevated
        (45.0, 1.20),

        # Both critical
        (70.0, 1.80),

        # Temperature critical
        (68.0, 0.50),

        # Vibration critical
        (42.0, 1.60),
    ]

    print()
    print("ZTII SHAP XAI ENGINE TEST")
    print("=" * 100)

    for temperature, vibration in test_cases:

        result = explain_prediction(
            temperature,
            vibration
        )

        print()

        print(
            f"Temperature: "
            f"{temperature:.2f} °C"
        )

        print(
            f"Vibration: "
            f"{vibration:.2f}"
        )

        print(
            f"Risk Prediction: "
            f"{result['risk_prediction']}%"
        )

        print(
            f"Primary Factor: "
            f"{result['primary_factor']}"
        )

        print(
            f"Temperature Contribution: "
            f"{result['temperature']}%"
        )

        print(
            f"Vibration Contribution: "
            f"{result['vibration']}%"
        )

        print(
            f"SHAP Temperature: "
            f"{result['shap_values']['temperature']}"
        )

        print(
            f"SHAP Vibration: "
            f"{result['shap_values']['vibration']}"
        )

        print(
            f"Explanation: "
            f"{result['explanation']}"
        )

    print()
    print("=" * 100)
    print("ZTII SHAP XAI TEST COMPLETE")