"""Read-only audit artifact wrapper; invoke through Docker's Django shell."""
import json
import os
from pathlib import Path
import runpy
from chatbot.knowledge_audit import audit


if __name__ in ('__main__', '<run_path>'):
    report = audit()
    Path(os.environ.get('PAULA_AUDIT_OUTPUT', 'PAULA_MVP_AUDIT_CURRENT.json')).write_text(json.dumps(report, indent=2))
    proof_path = Path('PAULA_MVP_INTEGRITY.json')
    if not proof_path.exists():
        proof_path.write_text(json.dumps({'before': runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()}, indent=2))
    print(json.dumps(report))
