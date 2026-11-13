"""A loja de teste (exemplos/loja-de-teste) servida de verdade, em
127.0.0.1: o monitor faz pedidos HTTP reais, mas nada sai da máquina."""

import functools
import re
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from openpyxl import load_workbook

from monitor_precos import cli
from monitor_precos.coleta import http_client
from monitor_precos.coleta.product_list import read_product_urls

EXAMPLES = Path(__file__).parents[1] / 'exemplos'
STORE = EXAMPLES / 'loja-de-teste'
ATTIC = 'catalogue/a-light-in-the-attic_1000/index.html'
NOTE = ('DEMONSTRAÇÃO: o preço de "A Light in the Attic" foi alterado na '
        'cópia local da loja de teste para mostrar o alerta.')


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # sem uma linha no terminal a cada pedido


@pytest.fixture
def store(tmp_path, monkeypatch):
    # Uma cópia da loja, para o teste mudar preços sem mexer no repositório.
    root = tmp_path / 'loja'
    shutil.copytree(STORE, root)
    server = ThreadingHTTPServer(
        ('127.0.0.1', 0),
        functools.partial(QuietHandler, directory=str(root)),
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # A pausa entre pedidos continua valendo, mas sem esperar de verdade.
    monkeypatch.setattr(http_client.time, 'sleep', lambda seconds: None)
    yield SimpleNamespace(root=root,
                          url=f'http://127.0.0.1:{server.server_port}/')
    server.shutdown()
    server.server_close()


def set_price(store, page, price):
    path = store.root / page
    html = re.sub(rb'(<p class="price_color">)[^<]*(</p>)',
                  rb'\g<1>' + price.encode() + rb'\g<2>',
                  path.read_bytes(), count=1)
    path.write_bytes(html)


def test_price_changed_in_the_test_store_becomes_an_alert(store, tmp_path,
                                                          capsys):
    products = tmp_path / 'produtos.csv'
    pages = [urlsplit(url).path.lstrip('/')
             for url in read_product_urls(EXAMPLES /
                                          'produtos-loja-de-teste.csv')]
    products.write_text('url\n' + ''.join(f'{store.url}{page}\n'
                                          for page in pages))
    report = tmp_path / 'demonstracao-alerta.xlsx'
    args = ['rodar', '--produtos', str(products), '--banco',
            str(tmp_path / 'demonstracao.db'), '--saida', str(report)]

    set_price(store, ATTIC, '£51.77')
    assert cli.main(args) == 0
    set_price(store, ATTIC, '£43.99')
    assert cli.main([*args, '--aviso', NOTE]) == 0

    out = capsys.readouterr().out
    assert ('3 produtos coletados · 1 alerta (variação de 5% ou mais) · '
            '0 problemas') in out
    assert ('  Caiu: A Light in the Attic, de £ 51,77 para £ 43,99 '
            '(-15,0%)') in out
    alerts = list(load_workbook(report)['Alertas'].iter_rows(
        values_only=True))
    assert alerts[1][0] == NOTE
    assert alerts[4][:4] == ('A Light in the Attic', 'Queda', 51.77, 43.99)


def test_product_list_of_the_test_store_points_to_its_pages():
    for url in read_product_urls(EXAMPLES / 'produtos-loja-de-teste.csv'):
        address = urlsplit(url)
        assert address.netloc == '127.0.0.1:8000'
        assert (STORE / address.path.lstrip('/')).is_file()
