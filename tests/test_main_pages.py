def test_info_pages(client):
    for path in ["/", "/licenses", "/privacy", "/terms", "/conduct", "/help"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200


def test_help_page_has_all_sections(client):
    r = client.get("/help")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'id="getting-started"' in body
    assert 'id="combat"' in body
    assert 'id="hoard-extraction"' in body
    assert 'id="skills-progression"' in body
