import json
from unittest.mock import Mock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scraper


BOOK_HTML = """
<div class="product_main">
    <h1>Test Book</h1>
    <p class="star-rating Three"></p>
    <p class="availability">In stock (22 available)</p>
</div>
<div id="product_description"></div>
<p>Test description.</p>
<table class="table-striped">
    <tr><th>UPC</th><td>abc123</td></tr>
    <tr><th>Product Type</th><td>Books</td></tr>
    <tr><th>Price (excl. tax)</th><td>£10.00</td></tr>
    <tr><th>Price (incl. tax)</th><td>£12.00</td></tr>
    <tr><th>Tax</th><td>£2.00</td></tr>
    <tr><th>Availability</th><td>In stock (22 available)</td></tr>
    <tr><th>Number of reviews</th><td>0</td></tr>
</table>
"""

BASE_URL = "https://books.toscrape.com/catalogue/"


def mock_response(html):
    """Создать ответ, похожий на результат requests.get."""
    response = Mock()
    response.text = html
    response.content = html.encode("utf-8")
    response.raise_for_status.return_value = None
    return response


def test_get_book_data(monkeypatch):
    """Проверить значения полей и отсутствие вложенности и дублей."""
    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda *args, **kwargs: mock_response(BOOK_HTML),
    )

    result = scraper.get_book_data(BASE_URL + "book/index.html")

    assert result == {
        "title": "Test Book",
        "rating": 3,
        "availability": 22,
        "description": "Test description.",
        "UPC": "abc123",
        "Product Type": "Books",
        "Price (excl. tax)": "£10.00",
        "Price (incl. tax)": "£12.00",
        "Tax": "£2.00",
        "Number of reviews": "0",
    }


def test_scrape_books_pagination(monkeypatch, tmp_path):
    """Проверить обход двух страниц и работу без сохранения."""
    pages = {
        BASE_URL + "page-1.html": """
            <article class="product_pod">
                <h3><a href="first/index.html">First</a></h3>
            </article>
            <li class="next"><a href="page-2.html">next</a></li>
        """,
        BASE_URL + "page-2.html": """
            <article class="product_pod">
                <h3><a href="second/index.html">Second</a></h3>
            </article>
        """,
    }

    get_page = Mock(
        side_effect=lambda url, **kwargs: mock_response(pages[url])
    )
    get_book = Mock(
        side_effect=lambda url: {"title": url}
    )

    monkeypatch.setattr(scraper.requests, "get", get_page)
    monkeypatch.setattr(scraper, "get_book_data", get_book)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.chdir(tmp_path)

    result = scraper.scrape_books(is_save=False)

    assert result == [
        {"title": BASE_URL + "first/index.html"},
        {"title": BASE_URL + "second/index.html"},
    ]
    assert [call.args[0] for call in get_page.call_args_list] == [
        BASE_URL + "page-1.html",
        BASE_URL + "page-2.html",
    ]
    assert get_book.call_count == 2
    assert not (tmp_path / "artifacts" / "books_data.txt").exists()


def test_scrape_books_save(monkeypatch, tmp_path):
    """Проверить сохранение данных в текстовый файл."""
    catalogue = """
        <article class="product_pod">
            <h3><a href="book/index.html">Книга</a></h3>
        </article>
    """
    book = {"title": "Тестовая книга", "rating": 3}

    monkeypatch.setattr(
        scraper.requests,
        "get",
        lambda *args, **kwargs: mock_response(catalogue),
    )
    monkeypatch.setattr(scraper, "get_book_data", lambda url: book)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.chdir(tmp_path)

    result = scraper.scrape_books(is_save=True)

    saved_file = tmp_path / "artifacts" / "books_data.txt"
    assert saved_file.exists()
    assert result == [book]
    assert json.loads(saved_file.read_text(encoding="utf-8")) == result