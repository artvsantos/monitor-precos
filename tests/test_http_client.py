import pytest
import requests

from monitor_precos.coleta.errors import CollectionError
from monitor_precos.coleta.http_client import USER_AGENT, PoliteClient
from tests.fakes import (
    ATTIC_URL,
    SAPIENS_URL,
    FakeClock,
    FakeResponse,
    FakeSession,
    attic,
)

ROBOTS = 'https://books.toscrape.com/robots.txt'
OTHER_SITE = 'https://quotes.toscrape.com/page/1/'


def make_client(pages, delay=2.0):
    session = FakeSession(pages)
    clock = FakeClock()
    client = PoliteClient(session, delay=delay, sleep=clock.sleep,
                          clock=clock.monotonic)
    return client, session, clock


def requested(session):
    return [url for url, headers, timeout in session.requested]


def test_returns_the_page_bytes_and_says_who_is_asking():
    client, session, clock = make_client({ATTIC_URL: attic()})

    content = client.fetch(ATTIC_URL)

    assert content == attic()
    assert requested(session) == [ROBOTS, ATTIC_URL]
    for _, headers, timeout in session.requested:
        assert headers['User-Agent'] == USER_AGENT
        assert timeout == 30


def test_generic_user_agent():
    # Um nome de robô, sem fingir ser navegador e sem dados de ninguém.
    assert USER_AGENT == 'monitor-precos/1.0'


def test_reads_robots_txt_once_per_site():
    client, session, clock = make_client({ATTIC_URL: attic(),
                                          SAPIENS_URL: attic()})

    client.fetch(ATTIC_URL)
    client.fetch(SAPIENS_URL)

    assert requested(session) == [ROBOTS, ATTIC_URL, SAPIENS_URL]


def test_page_forbidden_by_robots_txt_is_not_requested():
    rules = b'User-agent: *\nDisallow: /catalogue/\n'
    client, session, clock = make_client({ROBOTS: rules,
                                          ATTIC_URL: attic()})

    with pytest.raises(CollectionError,
                       match='o robots.txt do site não permite'):
        client.fetch(ATTIC_URL)

    assert requested(session) == [ROBOTS]


def test_rule_written_for_this_robot():
    rules = b'User-agent: monitor-precos\nDisallow: /\n'
    client, session, clock = make_client({ROBOTS: rules,
                                          ATTIC_URL: attic()})

    with pytest.raises(CollectionError):
        client.fetch(ATTIC_URL)


def test_page_allowed_by_robots_txt():
    rules = b'User-agent: *\nDisallow: /admin/\n'
    client, session, clock = make_client({ROBOTS: rules,
                                          ATTIC_URL: attic()})

    assert client.fetch(ATTIC_URL) == attic()


def test_robots_txt_that_forbids_robots_by_status():
    # 401 e 403 no robots.txt: o site não quer robôs.
    client, session, clock = make_client({ROBOTS: FakeResponse(403),
                                          ATTIC_URL: attic()})

    with pytest.raises(CollectionError, match='não permite'):
        client.fetch(ATTIC_URL)


@pytest.mark.parametrize('answer', [
    FakeResponse(503),
    requests.ConnectionError('sem rede'),
])
def test_unreadable_robots_txt_skips_the_site(answer):
    # Sem saber as regras, o mais seguro é não coletar desta vez.
    client, session, clock = make_client({ROBOTS: answer,
                                          ATTIC_URL: attic()})

    for url in (ATTIC_URL, SAPIENS_URL):
        with pytest.raises(CollectionError) as error:
            client.fetch(url)
        assert str(error.value) == (
            'não consegui ler o robots.txt de books.toscrape.com, então '
            'o site ficou de fora desta coleta'
        )

    assert requested(session) == [ROBOTS]


def test_waits_between_requests_to_the_same_site():
    client, session, clock = make_client({ATTIC_URL: attic(),
                                          SAPIENS_URL: attic()})

    client.fetch(ATTIC_URL)
    client.fetch(SAPIENS_URL)

    # Uma pausa antes da página (depois do robots.txt) e outra antes da
    # segunda página.
    assert clock.slept == [2.0, 2.0]


def test_waits_only_the_time_that_is_left():
    client, session, clock = make_client({ATTIC_URL: attic(),
                                          SAPIENS_URL: attic()})
    client.fetch(ATTIC_URL)
    clock.now += 1.5  # o resto do programa levou um tempo

    client.fetch(SAPIENS_URL)

    assert clock.slept == [2.0, 0.5]


def test_no_pause_when_enough_time_has_passed():
    client, session, clock = make_client({ATTIC_URL: attic(),
                                          SAPIENS_URL: attic()})
    client.fetch(ATTIC_URL)
    clock.now += 3

    client.fetch(SAPIENS_URL)

    assert clock.slept == [2.0]


def test_each_site_has_its_own_pause():
    other_robots = 'https://quotes.toscrape.com/robots.txt'
    client, session, clock = make_client({ATTIC_URL: attic(),
                                          OTHER_SITE: attic()})

    client.fetch(ATTIC_URL)
    client.fetch(OTHER_SITE)

    assert requested(session) == [ROBOTS, ATTIC_URL, other_robots,
                                  OTHER_SITE]
    assert clock.slept == [2.0, 2.0]


def test_crawl_delay_of_robots_txt_wins_when_longer():
    rules = b'User-agent: *\nCrawl-delay: 5\n'
    client, session, clock = make_client({ROBOTS: rules,
                                          ATTIC_URL: attic()})

    client.fetch(ATTIC_URL)

    assert clock.slept == [5.0]


def test_page_not_found():
    client, session, clock = make_client({})

    with pytest.raises(CollectionError) as error:
        client.fetch(ATTIC_URL)

    assert str(error.value) == (
        'página não encontrada (404): o produto pode ter saído do site'
    )


def test_server_error():
    client, session, clock = make_client({ATTIC_URL: FakeResponse(500)})

    with pytest.raises(CollectionError,
                       match='o site respondeu com erro 500'):
        client.fetch(ATTIC_URL)


def test_network_error():
    client, session, clock = make_client({
        ATTIC_URL: requests.Timeout('demorou'),
    })

    with pytest.raises(CollectionError,
                       match='não consegui acessar a página: demorou'):
        client.fetch(ATTIC_URL)


def test_uses_a_real_session_by_default():
    client = PoliteClient()

    assert isinstance(client.session, requests.Session)
    assert client.session.headers['User-Agent'] == USER_AGENT
