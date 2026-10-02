"""The layout clearance report must stay all-OK (AGENTS.md rule 4)."""

import pytest
from clearances import clearance_checks, report_clearances


def test_all_clearances_ok(items):
    low = [(n, v, need) for n, v, need in clearance_checks(items) if v < need]
    assert not low, "\n".join(f"{n}: {v:.2f} m < {need:.2f} m" for n, v, need in low)


def test_check_names_unique(items):
    names = [n for n, _, _ in clearance_checks(items)]
    assert len(names) == len(set(names))


def test_report_counts_low(items, capsys):
    assert report_clearances(items) == 0
    assert "OK" in capsys.readouterr().out


def test_report_flags_low_clearance(items, capsys):
    moved = [dict(i) for i in items]
    peninsula = next(i for i in moved if i["id"] == "peninsula")
    x0, x1, y0, y1 = peninsula["footprint"]
    peninsula["footprint"] = [x0, x1, y0 - 0.5, y1 - 0.5]  # squeeze the U aisle
    assert report_clearances(moved) > 0
    assert "LOW" in capsys.readouterr().out


def test_missing_item_raises(items):
    with pytest.raises(KeyError):
        clearance_checks([i for i in items if i["id"] != "sofa"])
