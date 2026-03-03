"""
SAP-style criticality mapping for Fiori UI (0-3).
1 = Error (Red), 2 = Warning (Yellow), 3 = Success (Green), 0 = Information
"""


def confidence_severity_to_criticality(confidence: float, severity: int) -> int:
    """
    Map confidence and failure severity to SAP Criticality (0-3).
    - No failure / high confidence No_Failure -> 3 (Success)
    - Failure with high severity or high confidence -> 1 (Error)
    - Failure with medium -> 2 (Warning)
    - Low confidence or info -> 0 (Information)
    """
    if severity == 0:
        return 3 if confidence >= 0.5 else 0  # No_Failure: Success or Info
    if confidence >= 0.85 and severity >= 4:
        return 1  # Error (Red)
    if confidence >= 0.6 or severity >= 3:
        return 2  # Warning (Yellow)
    return 0  # Information


def criticality_to_sap_label(criticality: int) -> str:
    if criticality == 1:
        return "Error"
    if criticality == 2:
        return "Warning"
    if criticality == 3:
        return "Success"
    return "Information"
