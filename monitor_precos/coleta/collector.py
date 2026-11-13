"""Coleta os produtos da lista, um por um."""

from collections.abc import Iterable, Iterator

from monitor_precos.coleta.books_toscrape import parse_product
from monitor_precos.coleta.errors import CollectionError
from monitor_precos.coleta.http_client import PoliteClient
from monitor_precos.coleta.product import Observation


def collect(urls: Iterable[str],
            client: PoliteClient) -> Iterator[Observation]:
    """Devolve cada produto assim que ele é coletado. Uma página com
    problema vira uma observação com o erro, e a coleta segue."""
    for url in urls:
        try:
            product = parse_product(client.fetch(url))
        except CollectionError as error:
            yield Observation(url, None, str(error))
        else:
            yield Observation(url, product, None)
