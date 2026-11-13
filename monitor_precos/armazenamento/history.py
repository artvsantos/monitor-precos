"""O histórico de preços num banco SQLite. Cada coleta fica guardada, e a
planilha compara a coleta de agora com a anterior."""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from monitor_precos.coleta.product import Observation

SCHEMA = """
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    collected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    collection_id INTEGER NOT NULL REFERENCES collections (id),
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    name TEXT,
    currency TEXT,
    price_cents INTEGER,
    in_stock INTEGER,
    stock INTEGER,
    error TEXT
);
CREATE INDEX IF NOT EXISTS prices_by_url ON prices (url, collection_id);
"""

PREVIOUS_PRICE = """
SELECT prices.price_cents, collections.collected_at
FROM prices JOIN collections ON collections.id = prices.collection_id
WHERE prices.url = ? AND prices.collection_id < ?
  AND prices.price_cents IS NOT NULL
ORDER BY prices.collection_id DESC
LIMIT 1
"""


@dataclass(frozen=True)
class PriceRow:
    """Um produto na coleta de agora, ao lado do preço da anterior."""

    url: str
    name: str | None
    currency: str | None
    price_cents: int | None
    in_stock: bool | None
    stock: int | None
    error: str | None
    previous_cents: int | None
    previous_at: datetime | None

    @property
    def change_cents(self) -> int | None:
        if self.price_cents is None or self.previous_cents is None:
            return None
        return self.price_cents - self.previous_cents

    @property
    def change(self) -> float | None:
        """A variação desde a coleta anterior, em fração: 0.05 é 5%."""
        if self.change_cents is None or not self.previous_cents:
            return None
        return self.change_cents / self.previous_cents


@dataclass(frozen=True)
class TimelineRow:
    """Um preço coletado, para a aba "Histórico"."""

    collected_at: datetime
    url: str
    name: str
    currency: str
    price_cents: int
    in_stock: bool


class PriceHistory:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def __enter__(self) -> 'PriceHistory':
        return self

    def __exit__(self, *error) -> None:
        self.db.close()

    def save(self, observations: Iterable[Observation],
             collected_at: datetime) -> int:
        # Uma transação só: a coleta entra inteira no histórico, ou não
        # entra.
        with self.db:
            collection = self.db.execute(
                'INSERT INTO collections (collected_at) VALUES (?)',
                (collected_at.isoformat(timespec='seconds'),),
            ).lastrowid
            self.db.executemany(
                'INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                [_values(collection, position, observation)
                 for position, observation in enumerate(observations)],
            )
        return collection

    def discard(self, collection: int) -> None:
        """Tira uma coleta do histórico, como se ela não tivesse
        acontecido."""
        with self.db:
            self.db.execute('DELETE FROM prices WHERE collection_id = ?',
                            (collection,))
            self.db.execute('DELETE FROM collections WHERE id = ?',
                            (collection,))

    def compare(self, collection: int) -> list[PriceRow]:
        rows = self.db.execute(
            'SELECT url, name, currency, price_cents, in_stock, stock, error '
            'FROM prices WHERE collection_id = ? ORDER BY position',
            (collection,),
        ).fetchall()
        return [self._compared(collection, *row) for row in rows]

    def timeline(self) -> list[TimelineRow]:
        rows = self.db.execute(
            'SELECT collections.collected_at, url, name, currency, '
            'price_cents, in_stock FROM prices JOIN collections '
            'ON collections.id = prices.collection_id '
            'WHERE price_cents IS NOT NULL '
            'ORDER BY collections.id, position',
        ).fetchall()
        return [
            TimelineRow(datetime.fromisoformat(collected_at), url, name,
                        currency, price, bool(in_stock))
            for collected_at, url, name, currency, price, in_stock in rows
        ]

    def _compared(self, collection, url, name, currency, price, in_stock,
                  stock, error) -> PriceRow:
        previous = self.db.execute(PREVIOUS_PRICE,
                                   (url, collection)).fetchone()
        if name is None:
            # A coleta deu erro: o nome vem da última vez que deu certo.
            known = self.db.execute(
                'SELECT name FROM prices WHERE url = ? AND name IS NOT NULL '
                'ORDER BY collection_id DESC LIMIT 1',
                (url,),
            ).fetchone()
            name = known[0] if known else None
        return PriceRow(
            url=url,
            name=name,
            currency=currency,
            price_cents=price,
            in_stock=None if in_stock is None else bool(in_stock),
            stock=stock,
            error=error,
            previous_cents=previous[0] if previous else None,
            previous_at=(datetime.fromisoformat(previous[1]) if previous
                         else None),
        )


def _values(collection: int, position: int, observation: Observation):
    product = observation.product
    if product is None:
        return (collection, position, observation.url, None, None, None,
                None, None, observation.error)
    return (collection, position, observation.url, product.name,
            product.currency, product.price_cents, product.in_stock,
            product.stock, None)
