"""Páginas salvas e um site falso, para os testes não usarem a internet."""

from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures'
ATTIC_URL = ('https://books.toscrape.com/catalogue/'
             'a-light-in-the-attic_1000/index.html')
SAPIENS_URL = ('https://books.toscrape.com/catalogue/'
               'sapiens-a-brief-history-of-humankind_996/index.html')


def page(name: str) -> bytes:
    """Uma página real do books.toscrape.com, salva em tests/fixtures."""
    return (FIXTURES / name).read_bytes()


def attic(price: str = '£51.77', availability: str | None = None) -> bytes:
    """A página do "A Light in the Attic", com o preço trocado se preciso."""
    html = page('a-light-in-the-attic.html').decode('utf-8')
    html = html.replace('£51.77', price)
    if availability is not None:
        html = html.replace('In stock (22 available)', availability)
    return html.encode('utf-8')


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b''):
        self.status_code = status_code
        self.content = content
        self.text = content.decode('utf-8', errors='replace')


class FakeSession:
    """Um site de mentira: cada URL devolve uma resposta ou um erro.

    URL que não está no dicionário devolve 404, como num site de verdade.
    """

    def __init__(self, pages: dict | None = None):
        self.pages = dict(pages or {})
        self.headers = {}
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append((url, dict(self.headers), timeout))
        answer = self.pages.get(url, FakeResponse(404))
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, bytes):
            return FakeResponse(200, answer)
        return answer


class FakeClock:
    """Relógio e sleep de mentira: o teste não espera de verdade."""

    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(round(seconds, 3))
        self.now += seconds
