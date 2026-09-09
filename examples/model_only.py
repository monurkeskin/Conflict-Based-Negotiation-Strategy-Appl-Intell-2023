"""Learn from four synthetic opponent offers; no negotiation framework required."""

import json
from pathlib import Path

from cbom import ConflictBasedOpponentModel, Preference

HERE = Path(__file__).resolve().parent
own = Preference.from_json(HERE / "profile_a.json")
model = ConflictBasedOpponentModel(own)
for line in (HERE / "offers.jsonl").read_text(encoding="utf-8").splitlines():
    model.update(json.loads(line))
print(json.dumps(model.preference.to_dict(), indent=2))
