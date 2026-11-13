import io
import runpy
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest
import requests
from openpyxl import load_workbook

from monitor_precos import cli
from monitor_precos.armazenamento.history import PriceHistory
from monitor_precos.coleta.http_client import PoliteClient
from tests.fakes import (
    ATTIC_URL,
    SAPIENS_URL,
    FakeResponse,
    FakeSession,
    attic,
    page,
)

MONDAY = datetime(2026, 11, 9, 8, 0)
TUESDAY = datetime(2026, 11, 10, 8, 0)


@pytest.fixture
def site(monkeypatch):
    """O site falso que o monitor visita, sem pausas de verdade."""
    session = FakeSession({ATTIC_URL: attic(),
                           SAPIENS_URL: page('sapiens.html')})
    monkeypatch.setattr(cli, 'make_client', lambda interval: PoliteClient(
        session, delay=interval, sleep=lambda seconds: None,
    ))
    monkeypatch.setattr(cli, 'now', lambda: MONDAY)
    return session


@pytest.fixture
def files(tmp_path):
    products = tmp_path / 'produtos.csv'
    products.write_text(f'url\n{ATTIC_URL}\n{SAPIENS_URL}\n')
    return SimpleNamespace(products=products, db=tmp_path / 'historico.db',
                           report=tmp_path / 'precos.xlsx')


def run(files, *extra):
    return cli.main(['rodar', '--produtos', str(files.products), '--banco',
                     str(files.db), '--saida', str(files.report), *extra])


def test_first_run(site, files, capsys):
    code = run(files)

    out = capsys.readouterr().out
    assert code == 0
    assert out.splitlines() == [
        f'Coletando 2 produtos de {files.products}, com pausa de 2 s entre '
        'os pedidos a cada site',
        '  A Light in the Attic: £ 51,77',
        '  Sapiens: A Brief History of Humankind: £ 54,23',
        '',
        f'Histórico em {files.db}',
        f'Planilha salva em {files.report}',
        '2 produtos coletados · 0 alertas (variação de 5% ou mais) · '
        '0 problemas',
    ]
    assert load_workbook(files.report).sheetnames[0] == 'Preços'


def test_second_run_shows_the_price_drop(site, files, capsys, monkeypatch):
    run(files)
    site.pages[ATTIC_URL] = attic(price='£45.99')
    monkeypatch.setattr(cli, 'now', lambda: TUESDAY)
    capsys.readouterr()

    run(files)

    out = capsys.readouterr().out
    assert ('2 produtos coletados · 1 alerta (variação de 5% ou mais) · '
            '0 problemas') in out
    assert ('  Caiu: A Light in the Attic, de £ 51,77 para £ 45,99 '
            '(-11,2%)') in out
    alerts = load_workbook(files.report)['Alertas']
    assert alerts['A4'].value == 'A Light in the Attic'
    assert alerts['B4'].value == 'Queda'


def test_price_rise_is_an_alert_too(site, files, capsys, monkeypatch):
    run(files)
    site.pages[ATTIC_URL] = attic(price='£57.00')
    monkeypatch.setattr(cli, 'now', lambda: TUESDAY)

    run(files)

    assert ('  Subiu: A Light in the Attic, de £ 51,77 para £ 57,00 '
            '(+10,1%)') in capsys.readouterr().out


def test_out_of_stock_and_errors_are_shown(site, files, capsys):
    site.pages[ATTIC_URL] = attic(availability='Out of stock')
    site.pages[SAPIENS_URL] = FakeResponse(500)

    code = run(files)

    out = capsys.readouterr().out
    assert code == 0
    assert '  A Light in the Attic: £ 51,77, sem estoque' in out
    assert f'  {SAPIENS_URL}: erro (o site respondeu com erro 500)' in out
    assert '1 produto coletado · 0 alertas' in out


def test_nothing_collected(site, files, capsys):
    # Sem internet, por exemplo. A planilha sai assim mesmo, com os
    # motivos, mas o código de saída avisa o agendador que deu errado.
    error = requests.ConnectionError('sem rede')
    site.pages.update({ATTIC_URL: error, SAPIENS_URL: error,
                       'https://books.toscrape.com/robots.txt': error})

    code = run(files)

    assert code == 1
    assert 'Nenhum produto foi coletado' in capsys.readouterr().err
    assert files.report.exists()


def test_note_goes_into_the_spreadsheet(site, files):
    note = 'DEMONSTRAÇÃO: preço alterado na cópia local.'

    run(files, '--aviso', note)

    assert load_workbook(files.report)['Preços']['A3'].value == note


def test_missing_product_list(site, files, capsys):
    files.products.unlink()

    assert run(files) == 1
    assert 'Não encontrei a lista de produtos' in capsys.readouterr().err


def test_spreadsheet_open_in_excel(site, files, capsys, monkeypatch):
    # No Windows, o Excel trava o arquivo aberto. A coleta não entra no
    # histórico: se entrasse, a variação de hoje nunca apareceria numa
    # planilha.
    def locked(*args, **kwargs):
        raise PermissionError

    monkeypatch.setattr(cli, 'write_report', locked)

    code = run(files)

    assert code == 1
    assert 'Ela está aberta no Excel?' in capsys.readouterr().err
    with PriceHistory(files.db) as history:
        assert history.timeline() == []


@pytest.mark.parametrize(('option', 'message'), [
    (['--intervalo', '0.5'], 'pelo menos 1 segundo'),
    (['--alerta', '0'], 'maior que zero'),
])
def test_invalid_options(files, capsys, option, message):
    with pytest.raises(SystemExit) as exit_info:
        run(files, *option)

    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err


def test_needs_a_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main([])

    assert exit_info.value.code == 2


def test_help_is_in_portuguese(capsys):
    with pytest.raises(SystemExit):
        cli.main(['rodar', '--help'])

    out = capsys.readouterr().out
    assert 'Coleta os preços agora' in out
    assert '--intervalo' in out


def test_runs_with_python_dash_m(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['monitor_precos', '--help'])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module('monitor_precos', run_name='__main__')

    assert exit_info.value.code == 0
    assert 'Monitora o preço' in capsys.readouterr().out


def test_output_without_reconfigure(site, files, monkeypatch):
    # Saída que não é um terminal comum (uma IDE, um log): o programa
    # imprime do mesmo jeito.
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, 'stdout', out)
    monkeypatch.setattr(sys, 'stderr', err)

    assert run(files) == 0
    assert 'Planilha salva em' in out.getvalue()


def test_make_client():
    client = cli.make_client(3)

    assert client.delay == 3
    assert isinstance(client.session, requests.Session)


def test_now_has_no_microseconds():
    assert cli.now().microsecond == 0
