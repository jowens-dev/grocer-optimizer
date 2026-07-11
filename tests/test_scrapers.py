from utils.scrapers import scrape_price


def test_scrape_price_extracts_price_from_html(monkeypatch):
    html = """
    <html><body>
    <script>window.__INITIAL_STATE__ = {"price": "$3.29"}</script>
    <div class="price">$3.29</div>
    </body></html>
    """

    class DummyResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self):
            return None

    monkeypatch.setattr("utils.scrapers.requests.get", lambda *args, **kwargs: DummyResponse(html))

    result = scrape_price("Walmart", "milk")

    assert result["store"] == "Walmart"
    assert result["product"] == "milk"
    assert result["price"] == 3.29
    assert result["source"] == "live"
