import ci_release_notes as n


def test_hms():
    assert n.hms(75) == "1 min 15 s"
    assert n.hms(3 * 3600 + 5 * 60) == "3 h 05 min"


def test_notes_table_and_totals(tmp_path):
    (tmp_path / "a.time").write_text("living_hero day 600\n")
    (tmp_path / "b.time").write_text("kitchen_u_evening evening 3000\n")
    rows = n.read_times(tmp_path)
    text = n.notes(rows, "256", "abc1234", 4000)
    assert "| living_hero | day | 10 min 00 s |" in text
    assert "| kitchen_u_evening | evening | 50 min 00 s |" in text
    assert "Total job time: **1 h 00 min** over 2 jobs" in text
    assert "1 h 07 min" in text and "256 samples" in text
