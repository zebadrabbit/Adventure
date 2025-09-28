def test_info_pages(client):
    for path in ["/", "/licenses", "/privacy", "/terms", "/conduct"]:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200
