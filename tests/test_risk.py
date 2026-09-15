import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fin_guard.backend.risk import calculate_risk, risk_level


def test_risk_bands():
    assert risk_level(10) == "Safe"
    assert risk_level(45) == "Monitor"
    assert risk_level(70) == "Warning"
    assert risk_level(95) == "Critical"


def test_circuit_breaker_thresholds():
    decision = calculate_risk(100, 100, 100, 20, 100)
    assert decision.triggered is True
    assert decision.level == "Critical"
