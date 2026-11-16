# Библиотеки, которые могут вам понадобиться
# При необходимости расширяйте список
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
import schedule
from bs4 import BeautifulSoup

RATING_VALUES = {
    "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
}

def get_book_data(book_url: str) -> dict:
    """Скачать страницу книги и вернуть сведения о ней.

    Args:
        book_url (str): Ссылка на страницу книги.

    Returns:
        dict: Название, рейтинг, количество в наличии, описание,
        UPC, тип продукта, цены без налога и с налогом, налог
        и количество отзывов.

    Raises:
        requests.RequestException: При сетевой ошибке или HTTP-ошибке.
        ValueError: Если обязательные элементы страницы отсутствуют.
    """
    response = requests.get(book_url, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    main = soup.select_one(".product_main")
    if main is None:
        raise ValueError(f"Не найдена карточка книги: {book_url}")

    title = main.find("h1")
    rating = main.select_one(".star-rating")
    stock = main.select_one(".availability")
    if any(node is None for node in (title, rating, stock)):
        raise ValueError(f"Не найдены обязательные поля: {book_url}")

    score = None
    for name in rating.get("class", []):
        if name in RATING_VALUES:
            score = RATING_VALUES[name]
            break

    stock_match = re.search(r"\d+", stock.get_text())

    description_heading = soup.select_one("#product_description")
    description = (
        description_heading.find_next_sibling("p")
        if description_heading is not None else None
    )

    book_data = {
        "title": title.get_text(strip=True),
        "rating": score,
        "availability": int(stock_match.group()) if stock_match else 0,
        "description": (
            description.get_text(" ", strip=True)
            if description is not None else ""
        ),
    }

    for row in soup.select("table.table-striped tr"):
        key, value = row.find("th"), row.find("td")
        if key is not None and value is not None:
            field = key.get_text(strip=True)
            if field != "Availability":
                book_data[field] = value.get_text(strip=True)

    return book_data

def scrape_books(
    is_save: bool = False,
    n: int | None = None,
) -> list[dict]:
    """Собрать данные о книгах каталога.

    Args:
        is_save (bool): Сохранить результат в books_data.txt.
        n (int | None): Максимальное число страниц.
            Если None, собрать все страницы.

    Returns:
        list[dict]: Данные о собранных книгах.

    Raises:
        ValueError: Если n не является положительным целым числом.
    """
    if n is not None and (type(n) is not int or n < 1):
        raise ValueError("n должно быть положительным целым числом")

    books = []
    page = 1

    while n is None or page <= n:
        page_url = (
            f"https://books.toscrape.com/catalogue/page-{page}.html"
        )
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        for link in soup.select("article.product_pod h3 a"):
            book_url = urljoin(page_url, link["href"])
            books.append(get_book_data(book_url))
            time.sleep(0.2)

        if soup.select_one("li.next a") is None:
            break

        page += 1

    if is_save:
        project_dir = Path.cwd()

        if project_dir.name == "notebooks":
            project_dir = project_dir.parent
            
        output_path = project_dir / "artifacts" / "books_data.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(books, file, ensure_ascii=False, indent=2)

        print(f"Файл сохранён: {output_path}")

    return books

def scheduled_scrape() -> None:
    """Собрать и сохранить книги; сообщить об ошибке, не остановив цикл."""
    try:
        books = scrape_books(is_save=True)
        print(f"Сохранено книг: {len(books)}")
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Выгрузка не выполнена: {error}")
        
def run_scheduler(at_time: str = "19:00") -> None:
    """Запустить ежедневную выгрузку в указанное местное время.
    
     Args:
        at_time (str): Время запуска в локальном часовом поясе компьютера.
    """
    scheduler = schedule.Scheduler()
    scheduler.every().day.at(at_time).do(scheduled_scrape)

    print(f"Ежедневная выгрузка в {at_time}")

    try:
        while True:
            scheduler.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Планировщик остановлен")