from datetime import datetime

from monitor_precos.armazenamento.history import PriceRow
from monitor_precos.relatorio.alerts import find_alerts, summary

BEFORE = datetime(2026, 11, 12, 8, 0)


def row(price, previous, name='Livro', error=None):
    return PriceRow(f'https://books.toscrape.com/{name}', name, '£', price,
                    True, None, error, previous,
                    BEFORE if previous else None)


def test_drops_and_rises_from_the_threshold_up():
    rows = [
        row(4750, 5000, 'caiu 5%'),
        row(5240, 5000, 'subiu 4,8%'),
        row(6000, 5000, 'subiu 20%'),
        row(5000, 5000, 'igual'),
        row(4000, None, 'primeira coleta'),
        row(None, 5000, 'erro', error='o site respondeu com erro 500'),
    ]

    alerts = find_alerts(rows, threshold=5)

    # Do maior para o menor, em valor absoluto.
    assert [alert.name for alert in alerts] == ['subiu 20%', 'caiu 5%']


def test_threshold_can_be_a_fraction_of_a_percent():
    assert find_alerts([row(5125, 5000)], threshold=2.5) == [row(5125, 5000)]
    assert find_alerts([row(5120, 5000)], threshold=2.5) == []


def test_summary():
    rows = [row(4500, 5000, 'A'), row(5000, 5000, 'B'),
            row(None, None, 'C', error='erro 500')]

    assert summary(rows, find_alerts(rows, 5), threshold=5) == (
        '2 produtos coletados · 1 alerta (variação de 5% ou mais) · '
        '1 problema'
    )


def test_summary_in_the_plural_and_with_a_decimal_threshold():
    rows = [row(4000, 5000, 'A'), row(6000, 5000, 'B')]

    assert summary(rows, find_alerts(rows, 2.5), threshold=2.5) == (
        '2 produtos coletados · 2 alertas (variação de 2,5% ou mais) · '
        '0 problemas'
    )
