from bot.songs import SongResult, button_label, format_duration


def test_format_duration():
    assert format_duration(185) == "3:05"
    assert format_duration(None) == ""


def test_button_label_truncates():
    s = SongResult("abcdefghijk", "x" * 100, 60)
    label = button_label(s)
    assert label.endswith("(1:00)")
    assert len(label) < 70
