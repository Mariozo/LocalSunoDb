import importlib
import json

import ls_web.app as app
from ls_core import wiring

mods = app._load_runtime_modules()

before = []
for module in mods:
    if "duration_sort_value" in vars(module):
        value = vars(module)["duration_sort_value"]
        before.append({
            "module": module.__name__,
            "block": wiring.module_block(module),
            "object_id": id(value),
            "repr": repr(value),
        })

exports_by_block = {}
flat = {}
duplicates = []
for module in mods:
    block = wiring.module_block(module)
    exports_by_block.setdefault(block, {})
    for name, value in wiring._exports(module).items():
        exports_by_block[block].setdefault(name, value)
        if name in flat and flat[name] is not value:
            if name == "duration_sort_value":
                duplicates.append({
                    "existing_repr": repr(flat[name]),
                    "new_module": module.__name__,
                    "new_repr": repr(value),
                    "existing_id": id(flat[name]),
                    "new_id": id(value),
                })
        else:
            flat.setdefault(name, value)

registry = wiring.wire_runtime(mods, {})
render = importlib.import_module("ls_library.render")

print("BEFORE=" + json.dumps(before, indent=2))
print("DUPLICATES=" + json.dumps(duplicates, indent=2))
print("REGISTRY_HAS=", "duration_sort_value" in registry, callable(registry.get("duration_sort_value")))
print("RENDER_HAS=", "duration_sort_value" in vars(render), callable(vars(render).get("duration_sort_value")))

assert "duration_sort_value" in registry
assert "duration_sort_value" not in vars(render), "Baseline unexpectedly wires duration_sort_value; regression not reproduced"
