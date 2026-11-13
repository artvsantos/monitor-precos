"""Linha de comando: python -m monitor_precos rodar."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from monitor_precos.armazenamento.history import PriceHistory
from monitor_precos.coleta.collector import collect
from monitor_precos.coleta.http_client import PoliteClient
from monitor_precos.coleta.product import Observation
from monitor_precos.coleta.product_list import (
    ProductListError,
    read_product_urls,
)
from monitor_precos.relatorio.alerts import find_alerts, summary
from monitor_precos.relatorio.spreadsheet import write_report
from monitor_precos.text import money, percent, plural

MIN_INTERVAL = 1.0


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def make_client(interval: float) -> PoliteClient:
    return PoliteClient(delay=interval)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='python -m monitor_precos',
        description=(
            'Monitora o preço de produtos em sites e monta uma planilha em '
            'Excel com o histórico e os alertas de variação.'
        ),
    )
    commands = parser.add_subparsers(dest='command', required=True,
                                     metavar='comando')
    run = commands.add_parser(
        'rodar', help='coleta os preços agora e atualiza a planilha',
        description=(
            'Coleta os preços agora, guarda no histórico e atualiza a '
            'planilha, com os alertas de variação desde a coleta anterior.'
        ),
    )
    run.add_argument('--produtos', default='produtos.csv',
                     help='lista com os endereços dos produtos, na coluna '
                          '"url" (padrão: produtos.csv)')
    run.add_argument('--banco', default='historico.db',
                     help='onde guardar o histórico (padrão: historico.db)')
    run.add_argument('--saida', default='precos.xlsx',
                     help='onde salvar a planilha (padrão: precos.xlsx)')
    run.add_argument('--alerta', type=float, default=5,
                     help='variação, em %%, que vira alerta (padrão: 5)')
    run.add_argument('--intervalo', type=float, default=2,
                     help='segundos de pausa entre os pedidos ao mesmo site '
                          '(padrão: 2; mínimo: 1)')
    run.add_argument('--aviso',
                     help='uma linha de texto para o topo da planilha')
    args = parser.parse_args(argv)
    if args.intervalo < MIN_INTERVAL:
        parser.error('--intervalo precisa ser de pelo menos 1 segundo, para '
                     'não sobrecarregar o site')
    if args.alerta <= 0:
        parser.error('--alerta precisa ser maior que zero')
    return args


def main(argv: list[str] | None = None) -> int:
    _safe_output()
    args = parse_args(argv)
    try:
        urls = read_product_urls(Path(args.produtos))
    except ProductListError as error:
        return fail(str(error))

    print(f"Coletando {plural(len(urls), 'produto', 'produtos')} de "
          f'{args.produtos}, com pausa de {args.intervalo:g} s entre os '
          'pedidos a cada site')
    collected_at = now()
    observations = []
    for observation in collect(urls, make_client(args.intervalo)):
        observations.append(observation)
        print(f'  {_describe(observation)}')

    output = Path(args.saida)
    with PriceHistory(Path(args.banco)) as history:
        collection = history.save(observations, collected_at)
        rows = history.compare(collection)
        try:
            write_report(output, rows, history.timeline(),
                         collected_at=collected_at, threshold=args.alerta,
                         note=args.aviso)
        except PermissionError:
            # Fora do histórico, a variação de hoje aparece na próxima
            # planilha, em vez de se perder.
            history.discard(collection)
            return fail(
                f'Não consegui salvar {output}. Ela está aberta no Excel? '
                'Feche a planilha e rode de novo; esta coleta não entrou no '
                'histórico.',
            )

    alerts = find_alerts(rows, args.alerta)
    print(f'\nHistórico em {args.banco}')
    print(f'Planilha salva em {output}')
    print(summary(rows, alerts, args.alerta))
    for row in alerts:
        print(f"  {'Caiu' if row.change < 0 else 'Subiu'}: {row.name}, de "
              f'{money(row.previous_cents, row.currency)} para '
              f'{money(row.price_cents, row.currency)} '
              f'({percent(row.change)})')
    if not any(row.error is None for row in rows):
        return fail('Nenhum produto foi coletado. Veja os motivos acima e na '
                    'aba "Problemas" da planilha.')
    return 0


def _describe(observation: Observation) -> str:
    product = observation.product
    if product is None:
        return f'{observation.url}: erro ({observation.error})'
    text = f'{product.name}: {money(product.price_cents, product.currency)}'
    return text if product.in_stock else f'{text}, sem estoque'


def _safe_output() -> None:
    # Agendado, o programa costuma escrever num arquivo de log, que no
    # Windows usa a codificação cp1252. Um nome de produto com caractere
    # fora dela derrubaria o programa; assim ele vira "?".
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='replace')


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1
