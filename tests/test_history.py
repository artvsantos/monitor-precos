from datetime import datetime

import pytest

from monitor_precos.armazenamento.history import (
    PriceHistory,
    PriceRow,
    TimelineRow,
)
from monitor_precos.coleta.product import Observation, Product
from tests.fakes import ATTIC_URL, SAPIENS_URL

MONDAY = datetime(2026, 11, 9, 8, 0)
TUESDAY = datetime(2026, 11, 10, 8, 0)
WEDNESDAY = datetime(2026, 11, 11, 8, 0)


def found(url, cents, name='A Light in the Attic', in_stock=True, stock=22):
    return Observation(url, Product(name, cents, '£', in_stock, stock), None)


def failed(url, error='o site respondeu com erro 500'):
    return Observation(url, None, error)


@pytest.fixture
def history(tmp_path):
    with PriceHistory(tmp_path / 'historico.db') as history:
        yield history


def test_first_collection_has_nothing_to_compare(history):
    collection = history.save([found(ATTIC_URL, 5177)], MONDAY)

    assert history.compare(collection) == [PriceRow(
        url=ATTIC_URL, name='A Light in the Attic', currency='£',
        price_cents=5177, in_stock=True, stock=22, error=None,
        previous_cents=None, previous_at=None,
    )]


def test_compares_with_the_previous_collection(history):
    history.save([found(ATTIC_URL, 5177)], MONDAY)
    collection = history.save([found(ATTIC_URL, 4599)], TUESDAY)

    [row] = history.compare(collection)

    assert row.price_cents == 4599
    assert row.previous_cents == 5177
    assert row.previous_at == MONDAY
    assert row.change == pytest.approx(-0.1116, abs=1e-4)


def test_failed_collection_is_skipped_when_comparing(history):
    # Se o site estava fora do ar na terça, a quarta compara com a segunda.
    history.save([found(ATTIC_URL, 5177)], MONDAY)
    history.save([failed(ATTIC_URL)], TUESDAY)
    collection = history.save([found(ATTIC_URL, 5500)], WEDNESDAY)

    [row] = history.compare(collection)

    assert (row.previous_cents, row.previous_at) == (5177, MONDAY)


def test_failed_product_keeps_its_last_known_name(history):
    history.save([found(ATTIC_URL, 5177)], MONDAY)
    collection = history.save([failed(ATTIC_URL),
                               failed(SAPIENS_URL)], TUESDAY)

    attic, sapiens = history.compare(collection)

    assert attic.name == 'A Light in the Attic'
    assert attic.error == 'o site respondeu com erro 500'
    assert attic.price_cents is None
    assert sapiens.name is None  # nunca foi coletado


def test_keeps_the_order_of_the_list(history):
    collection = history.save([found(SAPIENS_URL, 5423, name='Sapiens'),
                               found(ATTIC_URL, 5177)], MONDAY)

    assert [row.url for row in history.compare(collection)] == [
        SAPIENS_URL, ATTIC_URL,
    ]


def test_timeline_has_every_price_collected(history):
    history.save([found(ATTIC_URL, 5177)], MONDAY)
    history.save([found(ATTIC_URL, 4599, in_stock=False, stock=0),
                  failed(SAPIENS_URL)], TUESDAY)

    assert history.timeline() == [
        TimelineRow(MONDAY, ATTIC_URL, 'A Light in the Attic', '£', 5177,
                    True),
        TimelineRow(TUESDAY, ATTIC_URL, 'A Light in the Attic', '£', 4599,
                    False),
    ]


def test_history_stays_in_the_file(tmp_path):
    path = tmp_path / 'historico.db'
    with PriceHistory(path) as history:
        history.save([found(ATTIC_URL, 5177)], MONDAY)

    with PriceHistory(path) as history:
        collection = history.save([found(ATTIC_URL, 5177)], TUESDAY)
        [row] = history.compare(collection)

    assert row.previous_at == MONDAY


def test_discarded_collection_disappears(history):
    history.save([found(ATTIC_URL, 5177)], MONDAY)
    discarded = history.save([found(ATTIC_URL, 4599)], TUESDAY)

    history.discard(discarded)
    collection = history.save([found(ATTIC_URL, 4599)], WEDNESDAY)

    assert [item.collected_at for item in history.timeline()] == [
        MONDAY, WEDNESDAY,
    ]
    assert history.compare(collection)[0].previous_at == MONDAY


def test_folder_of_the_database_is_created(tmp_path):
    path = tmp_path / 'dados' / 'historico.db'

    with PriceHistory(path) as history:
        history.save([found(ATTIC_URL, 5177)], MONDAY)

    assert path.exists()


@pytest.mark.parametrize(('price', 'previous', 'change'), [
    (4599, None, None),     # primeira coleta
    (None, 5177, None),     # coleta com erro
    (500, 0, None),         # antes era de graça: não dá para calcular %
    (5500, 5000, 0.10),
    (4500, 5000, -0.10),
])
def test_change(price, previous, change):
    row = PriceRow(ATTIC_URL, 'Livro', '£', price, True, None, None,
                   previous, MONDAY)

    assert row.change == (pytest.approx(change) if change is not None
                          else None)


def test_change_in_cents():
    row = PriceRow(ATTIC_URL, 'Livro', '£', 4599, True, None, None, 5177,
                   MONDAY)

    assert row.change_cents == -578
    assert PriceRow(ATTIC_URL, 'Livro', '£', 4599, True, None, None, None,
                    None).change_cents is None
