"""Timeline roles, written into a TiLiA file after TiLiA has saved it."""
import json
from pathlib import Path


def set_roles(tla_path, roles: dict[str, dict[str, str]]) -> list[str]:
    """Give each timeline named in ``roles`` those fields in its ``metadata``, such as
    ``{"Structure": {"role": "form"}}``, and rewrite the file as TiLiA writes it (JSON, indent 2).

    TiLiA's current format reads ``role`` (and ``author``) from a timeline's ``metadata``
    (tilia_core's tla-1.0.0 schema); the TiLiA that saves these files (0.6.4 to 0.7) has no
    timeline metadata: it opens such a file but drops the field when it saves it. So this runs
    after TiLiA's last save, until TiLiA can set the field itself. Returns the names of
    ``roles`` that no timeline has.
    """
    path = Path(tla_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = set(roles)
    for timeline in data["timelines"].values():
        name = timeline.get("name")
        if name in roles:
            timeline.setdefault("metadata", {}).update(roles[name])
            missing.discard(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return sorted(missing)
