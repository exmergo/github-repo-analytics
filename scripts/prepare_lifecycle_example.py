"""Prepare a reviewable Dex edit payload; leave project files untouched."""

from pathlib import Path
import json
import yaml

root = Path(__file__).resolve().parents[1]
sql_path = root / "models/marts/fct_traffic.sql"
semantic_path = root / "models/semantic.yml"
content = sql_path.read_text()
if "has_page_views" in content:
    raise SystemExit("This example is already applied. Review or revert it before preparing again.")
content = content.replace(
    "1 as observed_days", "1 as observed_days, views_total > 0 as has_page_views"
)
semantic = yaml.safe_load(semantic_path.read_text())
model = next(m for m in semantic["semantic_models"] if m["name"] == "fct_traffic")
model["dimensions"].append(
    {
        "name": "has_page_views",
        "type": "categorical",
        "description": "Whether an observed traffic day has any page views.",
    }
)
payload = {
    "edits": [
        {
            "path": "models/marts/fct_traffic.sql",
            "kind": "model_sql",
            "op": "upsert",
            "content": content,
        },
        {
            "path": "models/semantic.yml",
            "kind": "semantic_yml",
            "op": "upsert",
            "content": yaml.safe_dump(semantic, sort_keys=False),
        },
    ]
}
output = root / ".data/tutorial-edits.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, indent=2) + "\n")
print(output)
