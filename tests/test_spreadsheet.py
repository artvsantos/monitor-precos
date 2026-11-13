from datetime import datetime

import pytest
from openpyxl import load_workbook

from monitor_precos.armazenamento.history import PriceRow, TimelineRow
from monitor_precos.relatorio.spreadsheet import write_report
from tests.fakes import ATTIC_URL, SAPIENS_URL

BEFORE = datetime(2026, 11, 12, 8, 0)
NOW = datetime(2026, 11, 13, 9, 30)
MISSING_URL = 'https://books.toscrape.com/catalogue/sumiu_1/index.html'

ATTIC = PriceRow(ATTIC_URL, 'A Light in the Attic', '£', 4599, True, 22,
                 None, 5177, BEFORE)
SAPIENS = PriceRow(SAPIENS_URL, 'Sapiens', '£', 5500, False, 0, None, 5423,
                   BEFORE)
MISSING = PriceRow(MISSING_URL, None, None, None, None, None,
                   'página não encontrada (404)', None, None)
TIMELINE = [
    TimelineRow(BEFORE, ATTIC_URL, 'A Light in the Attic', '£', 5177, True),
    TimelineRow(BEFORE, SAPIENS_URL, 'Sapiens', '£', 5423, True),
    TimelineRow(NOW, ATTIC_URL, 'A Light in the Attic', '£', 4599, True),
    TimelineRow(NOW, SAPIENS_URL, 'Sapiens', '£', 5500, False),
]


def report(tmp_path, rows=(ATTIC, SAPIENS, MISSING), timeline=TIMELINE,
           note=None):
    path = tmp_path / 'precos.xlsx'
    write_report(path, list(rows), timeline, collected_at=NOW, threshold=5,
                 note=note)
    return load_workbook(path)


def table(sheet, first_header):
    """As linhas da tabela, a partir do cabeçalho que começa com
    first_header."""
    rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    start = next(index for index, row in enumerate(rows)
                 if row[0] == first_header)
    return rows[start:]


def cell_of(sheet, value):
    return next(cell for row in sheet.iter_rows() for cell in row
                if cell.value == value)


def test_sheets(tmp_path):
    assert report(tmp_path).sheetnames == ['Preços', 'Alertas', 'Histórico',
                                           'Problemas']


def test_prices_sheet(tmp_path):
    sheet = report(tmp_path)['Preços']

    assert sheet['A1'].value == 'Preços coletados em 13/11/2026 09:30'
    assert sheet['A2'].value == ('2 produtos coletados · 1 alerta (variação '
                                 'de 5% ou mais) · 1 problema')
    header, attic, sapiens = table(sheet, 'Produto')
    assert header == ['Produto', 'Preço atual', 'Preço anterior', 'Variação',
                      'Variação (%)', 'Em estoque', 'Quantidade', 'Página']
    assert attic[:4] == ['A Light in the Attic', 45.99, 51.77, -5.78]
    assert attic[4] == pytest.approx(-0.11165, abs=1e-5)
    assert attic[5:] == ['Sim', 22, ATTIC_URL]
    assert sapiens[5:7] == ['Não', 0]


def test_prices_formats(tmp_path):
    sheet = report(tmp_path)['Preços']
    price = cell_of(sheet, 45.99)
    change = sheet.cell(price.row, 5)
    link = cell_of(sheet, ATTIC_URL)

    assert price.number_format == '"£" #,##0.00'
    assert change.number_format == '[Color10]▲ 0.0%;[Red]▼ 0.0%;0.0%'
    assert link.hyperlink.target == ATTIC_URL


def test_alerts_sheet(tmp_path):
    sheet = report(tmp_path)['Alertas']

    assert sheet['A1'].value == ('Alertas: variação de 5% ou mais desde a '
                                 'coleta anterior')
    header, attic = table(sheet, 'Produto')
    assert header == ['Produto', 'Tipo', 'Preço anterior', 'Preço atual',
                      'Variação (%)', 'Coleta anterior', 'Página']
    assert attic[:4] == ['A Light in the Attic', 'Queda', 51.77, 45.99]
    assert attic[5:] == [BEFORE, ATTIC_URL]


def test_no_alerts(tmp_path):
    steady = PriceRow(ATTIC_URL, 'A Light in the Attic', '£', 5177, True, 22,
                      None, 5177, BEFORE)
    sheet = report(tmp_path, rows=[steady])['Alertas']

    assert table(sheet, 'Produto')[1][0] == (
        'Nenhum produto mudou de preço 5% ou mais desde a coleta anterior.'
    )


def test_first_collection_has_no_alerts_to_show(tmp_path):
    first = PriceRow(ATTIC_URL, 'A Light in the Attic', '£', 5177, True, 22,
                     None, None, None)
    workbook = report(tmp_path, rows=[first], timeline=TIMELINE[:1])

    assert table(workbook['Alertas'], 'Produto')[1][0] == (
        'Primeira coleta: ainda não há preço anterior para comparar.'
    )
    assert table(workbook['Preços'], 'Produto')[1][:5] == [
        'A Light in the Attic', 51.77, None, None, None,
    ]


def test_history_sheet(tmp_path):
    rows = table(report(tmp_path)['Histórico'], 'Data da coleta')

    assert rows[0] == ['Data da coleta', 'Produto', 'Preço', 'Em estoque',
                       'Página']
    assert rows[1] == [BEFORE, 'A Light in the Attic', 51.77, 'Sim',
                       ATTIC_URL]
    assert rows[4] == [NOW, 'Sapiens', 55.0, 'Não', SAPIENS_URL]


def test_problems_sheet(tmp_path):
    rows = table(report(tmp_path)['Problemas'], 'Produto ou página')

    assert rows == [
        ['Produto ou página', 'Problema'],
        [MISSING_URL, 'página não encontrada (404)'],
    ]


def test_problem_shows_the_name_when_it_is_known(tmp_path):
    known = PriceRow(ATTIC_URL, 'A Light in the Attic', None, None, None,
                     None, 'o site respondeu com erro 500', 5177, BEFORE)

    rows = table(report(tmp_path, rows=[known])['Problemas'],
                 'Produto ou página')

    assert rows[1] == ['A Light in the Attic',
                       'o site respondeu com erro 500']


def test_no_problems(tmp_path):
    rows = table(report(tmp_path, rows=[ATTIC])['Problemas'],
                 'Produto ou página')

    assert rows[1] == ['Nenhum problema nesta coleta.', None]


def test_long_note_wraps_across_the_table(tmp_path):
    # O aviso não pode ficar cortado no fim da tabela.
    note = 'DEMONSTRAÇÃO: ' + 'texto longo, ' * 30

    workbook = report(tmp_path, note=note)

    prices = workbook['Preços']
    assert 'A3:H3' in prices.merged_cells
    assert prices['A3'].alignment.wrap_text is True
    assert prices.row_dimensions[3].height > 15
    assert 'A2:G2' in workbook['Alertas'].merged_cells


def test_headers_leave_room_for_the_filter_button(tmp_path):
    sheet = report(tmp_path)['Preços']

    # "Em estoque" tem 10 letras; o botão do filtro ocupa mais umas 3.
    assert sheet.column_dimensions['F'].width >= 15


def test_note_goes_on_the_prices_and_alerts_sheets(tmp_path):
    note = ('DEMONSTRAÇÃO: o preço foi alterado na cópia local da loja de '
            'teste para mostrar o alerta.')

    workbook = report(tmp_path, note=note)

    assert workbook['Preços']['A3'].value == note
    assert workbook['Alertas']['A2'].value == note
    assert table(workbook['Preços'], 'Produto')[1][0] == (
        'A Light in the Attic'
    )
