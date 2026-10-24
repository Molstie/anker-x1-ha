"""Tests for the kw44.3 read-only diagnostics: ac_active_power and battery_pack_power.

Same approach as tests/test_sensor_cleanup.py: `homeassistant` isn't installed,
so sensor.py / coordinator.py are checked by parsing the source with `ast`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.test_sensor_cleanup import (
    _load_coordinator_return_keys,
    _load_numeric_sensor_descriptions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
COORDINATOR_PY = REPO_ROOT / "custom_components" / "anker_x1" / "coordinator.py"
PACKAGE = REPO_ROOT / "custom_components" / "anker_x1"

NEW_KEYS = ("ac_active_power", "battery_pack_power")


def test_new_keys_are_in_the_coordinator_data_dict():
    keys = _load_coordinator_return_keys()
    for key in NEW_KEYS:
        assert key in keys


def test_new_sensors_are_diagnostic_power_measurements():
    descs = _load_numeric_sensor_descriptions()
    for key in NEW_KEYS:
        d = descs[key]
        assert d["native_unit_of_measurement"] == "UnitOfPower.WATT"
        assert d["device_class"] == "SensorDeviceClass.POWER"
        assert d["state_class"] == "SensorStateClass.MEASUREMENT"
        assert d["entity_category"] == "EntityCategory.DIAGNOSTIC"
        # enabled by default: the opt-out flag must not be set
        assert "entity_registry_enabled_default" not in d


def test_pack_power_is_its_own_optional_block():
    """10254 goes through the tolerant reader in its own block, so a unit that
    lacks it keeps the pack voltage (block H, 10253)."""
    tree = ast.parse(COORDINATOR_PY.read_text())
    blocks = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_read_optional_block"
        ):
            name, addr, count = (ast.literal_eval(a) for a in node.args)
            blocks[name] = (addr, count)
    assert blocks["P"] == (10254, 2)
    assert blocks["H"] == (10253, 1)


def test_ac_active_power_is_exposed_raw():
    """The data dict carries the raw register value, not a corrected one."""
    tree = ast.parse(COORDINATOR_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "ac_active_power":
                    assert ast.unparse(v) == "ac_active_power"
                    return
    raise AssertionError("ac_active_power not in a returned dict")


def test_no_new_write_calls():
    """kw44.3 is read-only: the set of write sites is unchanged from kw44.2
    (battery setpoint, work mode, export/import limits, restore, watchdog)."""
    writes = []
    for py in sorted(PACKAGE.glob("*.py")):
        for i, line in enumerate(py.read_text().splitlines(), 1):
            if re.search(r"\bwrite_registers?\b", line):
                writes.append(f"{py.name}:{line.strip()}")
    assert len(writes) == 10, writes
