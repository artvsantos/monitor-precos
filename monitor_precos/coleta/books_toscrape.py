"""Lê a página de um produto no books.toscrape.com, o site de treino de
coleta de dados usado neste projeto.

Para monitorar outro site, este é o arquivo a escrever de novo: cada loja
organiza a página do produto de um jeito.
"""

import re
from decimal import Decimal

from bs4 import BeautifulSoup

from monitor_precos.coleta.errors import CollectionError
from monitor_precos.coleta.product import Product

PRICE = re.compile(r'(?P<currency>[^\d\s]+)\s*(?P<amount>\d[\d,]*\.\d\d)')
STOCK = re.compile(r'\((\d+) available\)')


def parse_product(html: bytes) -> Product:
    # Bytes, e não texto: o site não diz a codificação no cabeçalho HTTP,
    # só no <meta> da página, que o BeautifulSoup lê. Como texto, a libra
    # viraria "Â£".
    page = BeautifulSoup(html, 'html.parser')
    main = page.select_one('div.product_main')
    if (main is None or main.h1 is None
            or main.select_one('p.price_color') is None
            or main.select_one('p.availability') is None):
        raise CollectionError(
            'não reconheci a página do produto: o site pode ter mudado o '
            'layout ou o endereço não é de um produto',
        )

    price = main.select_one('p.price_color').get_text(strip=True)
    match = PRICE.fullmatch(price)
    if match is None:
        raise CollectionError(f'"{price}" não é um preço')
    # Formato inglês: vírgula separa os milhares, ponto os centavos.
    cents = int(Decimal(match['amount'].replace(',', '')) * 100)

    availability = ' '.join(main.select_one('p.availability').get_text()
                            .split())
    in_stock = availability.lower().startswith('in stock')
    stock = STOCK.search(availability)
    return Product(
        name=main.h1.get_text(strip=True),
        price_cents=cents,
        currency=match['currency'],
        in_stock=in_stock,
        stock=int(stock[1]) if stock else (None if in_stock else 0),
    )
