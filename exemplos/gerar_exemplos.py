"""Gera as planilhas de exemplo desta pasta. Na raiz do projeto:

    venv\\Scripts\\python exemplos\\gerar_exemplos.py

1. precos.xlsx e historico.db: duas coletas de verdade no books.toscrape.com,
   um site feito para treinar coleta de dados, com a pausa normal entre os
   pedidos. Os preços de lá não mudam, então a variação dá 0% e a aba
   "Alertas" fica sem nenhum alerta.

2. demonstracao-alerta.xlsx: duas coletas na loja de teste, uma cópia local
   de três páginas do books.toscrape.com servida em 127.0.0.1:8000. Entre
   uma coleta e outra, o preço de um livro é alterado numa cópia
   temporária da loja, só para mostrar o alerta. A planilha avisa isso no
   topo das abas "Preços" e "Alertas".
"""

import functools
import re
import shutil
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from monitor_precos import cli  # noqa: E402

ATTIC = 'catalogue/a-light-in-the-attic_1000/index.html'
NOTE = (
    'DEMONSTRAÇÃO: o preço de "A Light in the Attic" foi alterado de '
    '£ 51,77 para £ 43,99 na cópia local da loja de teste, só para mostrar '
    'o alerta. Os outros dados vêm das páginas reais do books.toscrape.com.'
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def real_collection() -> None:
    database = HERE / 'historico.db'
    database.unlink(missing_ok=True)
    args = ['rodar', '--produtos', str(HERE / 'produtos.csv'),
            '--banco', str(database), '--saida', str(HERE / 'precos.xlsx')]
    for _ in range(2):
        if cli.main(args) != 0:
            raise SystemExit('A coleta no books.toscrape.com falhou.')


def demonstration() -> None:
    with tempfile.TemporaryDirectory() as temp:
        store = Path(temp) / 'loja'
        shutil.copytree(HERE / 'loja-de-teste', store)
        server = ThreadingHTTPServer(
            ('127.0.0.1', 8000),
            functools.partial(QuietHandler, directory=str(store)),
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            args = ['rodar',
                    '--produtos', str(HERE / 'produtos-loja-de-teste.csv'),
                    '--banco', str(Path(temp) / 'demonstracao.db'),
                    '--saida', str(HERE / 'demonstracao-alerta.xlsx')]
            cli.main(args)
            page = store / ATTIC
            page.write_bytes(re.sub(
                rb'(<p class="price_color">)[^<]*(</p>)',
                lambda match: match[1] + '£43.99'.encode() + match[2],
                page.read_bytes(), count=1,
            ))
            cli.main([*args, '--aviso', NOTE])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    real_collection()
    print()
    demonstration()
