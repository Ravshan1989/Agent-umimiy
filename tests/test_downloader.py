from bot.downloader import extract_url


def test_extract_url_from_text():
    assert extract_url("mana: https://www.instagram.com/reel/abc/ ok") == "https://www.instagram.com/reel/abc/"


def test_extract_url_none():
    assert extract_url("salom") is None
    assert extract_url("") is None
