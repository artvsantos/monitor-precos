"""Busca as páginas com educação: lê o robots.txt de cada site, espera
entre um pedido e outro ao mesmo site e se identifica como robô."""

import time
from urllib.parse import SplitResult, urlsplit
from urllib.robotparser import RobotFileParser

import requests

from monitor_precos.coleta.errors import CollectionError

# Um nome de robô, sem fingir ser navegador.
USER_AGENT = 'monitor-precos/1.0'
TIMEOUT = 30


class PoliteClient:
    def __init__(self, session=None, *, delay: float = 2.0, sleep=None,
                 clock=None) -> None:
        self.session = session if session is not None else requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT
        self.delay = delay
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        # Por site: as regras do robots.txt (None se não deu para ler) e a
        # hora do último pedido.
        self._rules: dict[str, RobotFileParser | None] = {}
        self._last_request: dict[str, float] = {}

    def fetch(self, url: str) -> bytes:
        site = urlsplit(url)
        if site.netloc not in self._rules:
            self._rules[site.netloc] = self._read_robots(site)
        rules = self._rules[site.netloc]
        if rules is None:
            raise CollectionError(
                f'não consegui ler o robots.txt de {site.netloc}, então o '
                'site ficou de fora desta coleta',
            )
        if not rules.can_fetch(USER_AGENT, url):
            raise CollectionError(
                'o robots.txt do site não permite coletar esta página',
            )

        delay = max(self.delay, rules.crawl_delay(USER_AGENT) or 0)
        response = self._get(site.netloc, url, delay)
        if response.status_code == 404:
            raise CollectionError(
                'página não encontrada (404): o produto pode ter saído do '
                'site',
            )
        if response.status_code != 200:
            raise CollectionError(
                f'o site respondeu com erro {response.status_code}',
            )
        return response.content

    def _read_robots(self, site: SplitResult) -> RobotFileParser | None:
        url = f'{site.scheme}://{site.netloc}/robots.txt'
        try:
            response = self._get(site.netloc, url, self.delay)
        except CollectionError:
            return None
        rules = RobotFileParser(url)
        if response.status_code == 200:
            rules.parse(response.text.splitlines())
        elif response.status_code in (401, 403):
            rules.disallow_all = True
        elif response.status_code >= 500:
            # Sem saber as regras, o mais seguro é não coletar desta vez.
            return None
        else:
            rules.allow_all = True  # sem robots.txt: sem restrições
        return rules

    def _get(self, host: str, url: str, delay: float):
        last = self._last_request.get(host)
        if last is not None:
            wait = delay - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        try:
            return self.session.get(url, timeout=TIMEOUT)
        except requests.RequestException as error:
            raise CollectionError(
                f'não consegui acessar a página: {error}',
            ) from None
        finally:
            self._last_request[host] = self._clock()
