from monitor_precos.coleta.collector import collect
from monitor_precos.coleta.http_client import PoliteClient
from monitor_precos.coleta.product import Observation
from tests.fakes import (
    ATTIC_URL,
    SAPIENS_URL,
    FakeClock,
    FakeSession,
    attic,
    page,
)


def test_collects_each_url_and_keeps_going_after_an_error():
    clock = FakeClock()
    session = FakeSession({ATTIC_URL: attic(),
                           SAPIENS_URL: page('sapiens.html')})
    missing = 'https://books.toscrape.com/catalogue/sumiu_1/index.html'
    client = PoliteClient(session, sleep=clock.sleep, clock=clock.monotonic)

    observations = list(collect([ATTIC_URL, missing, SAPIENS_URL], client))

    assert [observation.url for observation in observations] == [
        ATTIC_URL, missing, SAPIENS_URL,
    ]
    assert observations[0].product.name == 'A Light in the Attic'
    assert observations[1] == Observation(
        missing, None,
        'página não encontrada (404): o produto pode ter saído do site',
    )
    assert observations[2].product.price_cents == 5423


def test_page_that_changed_layout_becomes_an_error():
    clock = FakeClock()
    session = FakeSession({ATTIC_URL: b'<html><p>em manutencao</p></html>'})
    client = PoliteClient(session, sleep=clock.sleep, clock=clock.monotonic)

    [observation] = collect([ATTIC_URL], client)

    assert observation.product is None
    assert 'não reconheci a página' in observation.error
