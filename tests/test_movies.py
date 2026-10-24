from bot.movies import MovieMatch, format_match, parse_claude_reply, parse_trace


def test_parse_trace_ok():
    data = {"result": [{"similarity": 0.97, "episode": 3, "from": 125.4,
                        "anilist": {"title": {"english": None, "romaji": "Naruto"}}}]}
    m = parse_trace(data)
    assert m.title == "Naruto" and m.detail == "3-qism, 02:05"


def test_parse_trace_low_similarity():
    assert parse_trace({"result": [{"similarity": 0.5, "anilist": {"title": {"romaji": "X"}}}]}) is None
    assert parse_trace({"result": []}) is None


def test_parse_claude_reply():
    m = parse_claude_reply('Mana: {"title": "Titanic", "year": 1997, "type": "kino", "confidence": "yuqori", "reason": "kema"}')
    assert m.title == "Titanic" and m.year == 1997


def test_parse_claude_reply_unknown_or_bad():
    assert parse_claude_reply('{"title": null, "confidence": "past"}') is None
    assert parse_claude_reply('{"title": "A", "confidence": "past"}') is None
    assert parse_claude_reply("topolmadim") is None


def test_format_match_claude_has_warning():
    text = format_match(MovieMatch("Titanic", "claude", year=1997, confidence="o'rta"))
    assert "Titanic" in text and "xato bo'lishi mumkin" in text
