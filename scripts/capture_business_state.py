"""Read-only, timestamped witnesses after the business test, including failed runs."""
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = os.getenv('BANKPULSE_URL', 'http://localhost:18080')
OUT = Path('artifacts/business')
OUT.mkdir(parents=True, exist_ok=True)


def utc():
    return datetime.now(timezone.utc).isoformat()


def observe(route):
    started = utc()
    try:
        with urllib.request.urlopen(BASE + route, timeout=5) as response:
            return {'startedAt': started, 'observedAt': utc(), 'http': response.status,
                    'body': json.load(response)}
    except Exception as error:
        return {'startedAt': started, 'observedAt': utc(), 'error': repr(error)}


witness = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
           'startedAt': utc(), 'scope': 'post-test observations; does not replace the business oracle'}
input_path = OUT / 'result.json'
if input_path.exists():
    business = json.loads(input_path.read_text())
    witness['fixtureRunId'] = business['fixtureRunId']
    witness['cases'] = {}
    for name in ('under', 'over', 'healthy'):
        case = business.get('observations', {}).get(name, {})
        aggregate_id = case.get('persisted', {}).get('id')
        if aggregate_id:
            witness['cases'][name] = {
                'aggregate': observe('/api/splits/' + urllib.parse.quote(aggregate_id)),
                'projection': observe('/api/business/snapshot?fixtureRunId=' +
                    urllib.parse.quote(business['fixtureRunId'] + '-' + name)),
            }
else:
    witness['reason'] = 'business test produced no result.json'
witness['services'] = {name: observe('/health/' + name) for name in
                      ('payments', 'audit', 'experiences', 'travel', 'events', 'social-split')}
witness['snapshot'] = observe('/api/business/snapshot')
witness['completedAt'] = utc()
(OUT / 'current-state.json').write_text(json.dumps(witness, indent=2) + '\n')
print('Saved contemporaneous aggregate, KPI and health evidence:', OUT / 'current-state.json')
