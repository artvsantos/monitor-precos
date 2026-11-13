import pytest

from monitor_precos.coleta.books_toscrape import parse_product
from monitor_precos.coleta.errors import CollectionError
from monitor_precos.coleta.product import Product
from tests.fakes import attic, page


def test_reads_name_price_and_stock_from_a_real_page():
    product = parse_product(page('a-light-in-the-attic.html'))

    assert product == Product(
        name='A Light in the Attic',
        price_cents=5177,
        currency='£',
        in_stock=True,
        stock=22,
    )


def test_reads_another_real_page():
    product = parse_product(page('sapiens.html'))

    assert product.name == 'Sapiens: A Brief History of Humankind'
    assert product.price_cents == 5423
    assert product.currency == '£'


def test_page_without_declared_encoding_keeps_the_pound_sign():
    # O site manda "text/html" sem charset: lida como texto pelo requests,
    # a libra virava "Â£". Lendo os bytes, vale o <meta charset> da página.
    assert parse_product(attic()).currency == '£'


def test_price_with_thousands_separator():
    assert parse_product(attic(price='£1,234.50')).price_cents == 123450


def test_out_of_stock():
    product = parse_product(attic(availability='Out of stock'))

    assert product.in_stock is False
    assert product.stock == 0


def test_in_stock_without_quantity():
    product = parse_product(attic(availability='In stock'))

    assert product.in_stock is True
    assert product.stock is None


def test_page_that_is_not_a_product():
    with pytest.raises(CollectionError, match='não reconheci a página'):
        parse_product(b'<html><body><h1>Oops</h1></body></html>')


def test_price_that_is_not_a_number():
    with pytest.raises(CollectionError, match='"Esgotado" não é um preço'):
        parse_product(attic(price='Esgotado'))
