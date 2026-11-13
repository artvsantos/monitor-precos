"""A planilha em Excel: os preços de agora, os alertas, o histórico e o
que deu problema na coleta."""

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from monitor_precos.armazenamento.history import PriceRow, TimelineRow
from monitor_precos.relatorio.alerts import (
    find_alerts,
    summary,
    threshold_text,
)

HEADER_FONT = Font(bold=True, color='FFFFFF')
HEADER_FILL = PatternFill('solid', fgColor='4F46E5')
TITLE_FONT = Font(bold=True, size=14)
NOTE_FONT = Font(bold=True, color='B45309')
# Subiu: verde, com ▲. Caiu: vermelho, com ▼.
CHANGE_FORMAT = '[Color10]▲ 0.0%;[Red]▼ 0.0%;0.0%'
DATE_FORMAT = 'dd/mm/yyyy hh:mm'


@dataclass(frozen=True)
class Money:
    cents: int | None
    currency: str | None
    signed: bool = False


@dataclass(frozen=True)
class Change:
    fraction: float | None


@dataclass(frozen=True)
class Link:
    url: str


def write_report(path: Path, rows: list[PriceRow],
                 timeline: list[TimelineRow], *, collected_at: datetime,
                 threshold: float, note: str | None = None) -> None:
    alerts = find_alerts(rows, threshold)
    workbook = Workbook()
    _prices(workbook.active, rows, alerts, collected_at, threshold, note)
    _alerts(workbook.create_sheet('Alertas'), rows, alerts, threshold, note)
    _timeline(workbook.create_sheet('Histórico'), timeline)
    _problems(workbook.create_sheet('Problemas'), rows)
    workbook.save(path)


def _prices(sheet, rows, alerts, collected_at, threshold, note) -> None:
    sheet.title = 'Preços'
    title = f'Preços coletados em {collected_at:%d/%m/%Y %H:%M}'
    first, note_row = _heading(sheet, title,
                               summary(rows, alerts, threshold), note)
    headers = ['Produto', 'Preço atual', 'Preço anterior', 'Variação',
               'Variação (%)', 'Em estoque', 'Quantidade', 'Página']
    _table(sheet, first, headers, [
        [row.name, Money(row.price_cents, row.currency),
         Money(row.previous_cents, row.currency),
         Money(row.change_cents, row.currency, signed=True),
         Change(row.change), _yes_no(row.in_stock), row.stock,
         Link(row.url)]
        for row in rows if row.error is None
    ])
    _wrap_note(sheet, note_row, len(headers))


def _alerts(sheet, rows, alerts, threshold, note) -> None:
    limit = threshold_text(threshold)
    first, note_row = _heading(sheet, f'Alertas: variação de {limit} ou '
                                      'mais desde a coleta anterior',
                               None, note)
    headers = ['Produto', 'Tipo', 'Preço anterior', 'Preço atual',
               'Variação (%)', 'Coleta anterior', 'Página']
    body = [
        [row.name, 'Queda' if row.change < 0 else 'Alta',
         Money(row.previous_cents, row.currency),
         Money(row.price_cents, row.currency), Change(row.change),
         row.previous_at, Link(row.url)]
        for row in alerts
    ]
    if not body and any(row.previous_cents is not None for row in rows):
        body = [[f'Nenhum produto mudou de preço {limit} ou mais desde a '
                 'coleta anterior.']]
    elif not body:
        body = [['Primeira coleta: ainda não há preço anterior para '
                 'comparar.']]
    _table(sheet, first, headers, body)
    _wrap_note(sheet, note_row, len(headers))


def _timeline(sheet, timeline) -> None:
    _table(sheet, 1, ['Data da coleta', 'Produto', 'Preço', 'Em estoque',
                      'Página'], [
        [item.collected_at, item.name, Money(item.price_cents, item.currency),
         _yes_no(item.in_stock), Link(item.url)]
        for item in timeline
    ])


def _problems(sheet, rows) -> None:
    problems = [[row.name or row.url, row.error] for row in rows if row.error]
    _table(sheet, 1, ['Produto ou página', 'Problema'],
           problems or [['Nenhum problema nesta coleta.']])


def _heading(sheet: Worksheet, title: str, subtitle: str | None,
             note: str | None) -> tuple[int, int | None]:
    """Escreve o título e as linhas embaixo dele. Devolve a linha onde a
    tabela começa e a linha do aviso, se houver."""
    sheet['A1'] = title
    sheet['A1'].font = TITLE_FONT
    row = 2
    if subtitle:
        sheet.cell(row, 1, subtitle)
        row += 1
    note_row = None
    if note:
        sheet.cell(row, 1, note).font = NOTE_FONT
        note_row = row
        row += 1
    return row + 1, note_row


def _wrap_note(sheet: Worksheet, row: int | None, columns: int) -> None:
    """O aviso ocupa a largura da tabela e quebra em linhas: ele não pode
    ficar cortado."""
    if row is None:
        return
    sheet.merge_cells(start_row=row, start_column=1, end_row=row,
                      end_column=columns)
    cell = sheet.cell(row, 1)
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    width = sum(sheet.column_dimensions[get_column_letter(column)].width
                for column in range(1, columns + 1))
    # Em negrito, cada letra ocupa um pouco mais que a largura-padrão.
    lines = math.ceil(len(cell.value) * 1.2 / width)
    sheet.row_dimensions[row].height = 15 * lines


def _table(sheet: Worksheet, first: int, headers: list[str],
           body: list[list]) -> None:
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(first, column, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
    for row, values in enumerate(body, start=first + 1):
        for column, value in enumerate(values, start=1):
            _put(sheet.cell(row, column), value)
    sheet.freeze_panes = sheet.cell(first + 1, 1)
    sheet.auto_filter.ref = (f'A{first}:{get_column_letter(len(headers))}'
                             f'{first + len(body)}')
    _fit_columns(sheet, first, len(headers))


def _put(cell, value) -> None:
    if isinstance(value, Money):
        if value.cents is not None:
            cell.value = value.cents / 100
            amount = f'"{value.currency}" #,##0.00'
            cell.number_format = (f'+{amount};-{amount};{amount}'
                                  if value.signed else amount)
    elif isinstance(value, Change):
        if value.fraction is not None:
            cell.value = value.fraction
            cell.number_format = CHANGE_FORMAT
    elif isinstance(value, Link):
        cell.value = value.url
        cell.hyperlink = value.url
        cell.style = 'Hyperlink'
    elif isinstance(value, datetime):
        cell.value = value
        cell.number_format = DATE_FORMAT
    else:
        cell.value = value


def _yes_no(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _fit_columns(sheet: Worksheet, first: int, columns: int) -> None:
    for column in range(1, columns + 1):
        # O cabeçalho precisa de folga para o botão do filtro.
        header = len(str(sheet.cell(first, column).value)) + 5
        values = [len(str(sheet.cell(row, column).value or '')) + 2
                  for row in range(first + 1, sheet.max_row + 1)]
        sheet.column_dimensions[get_column_letter(column)].width = min(
            max([header, 12, *values]), 60,
        )
