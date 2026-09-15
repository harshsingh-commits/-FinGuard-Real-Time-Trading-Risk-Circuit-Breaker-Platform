import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fin_guard.database.storage import Storage


def test_checkpoint_recovery_and_audit_storage(tmp_path):
    storage = Storage(tmp_path / "audit.db")
    state = {"timestamp": "2026-01-01T00:00:00+00:00", "risk_score": 91, "risk_level": "Critical", "circuit_breaker_triggered": True, "circuit_breaker_reason": "test", "audit_log": [{"timestamp": "2026-01-01T00:00:00+00:00", "event": "risk_calculated"}]}
    storage.save_state(state, "incident-1")
    checkpoints = storage.list_rows("checkpoints")
    incidents = storage.list_rows("incidents")
    audits = storage.list_rows("audit_logs")
    assert checkpoints[0]["thread_id"] == "incident-1"
    assert incidents[0]["risk_score"] == 91
    assert audits[0]["event"] == "risk_calculated"
