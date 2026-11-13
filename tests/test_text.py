import pytest

from monitor_precos.text import money, percent, plural


@pytest.mark.parametrize(('count', 'expected'), [
    (0, '0 produtos'),
    (1, '1 produto'),
    (2, '2 produtos'),
    (1234, '1.234 produtos'),
])
def test_plural(count, expected):
    assert plural(count, 'produto', 'produtos') == expected


@pytest.mark.parametrize(('cents', 'expected'), [
    (5177, '£ 51,77'),
    (123450, '£ 1.234,50'),
    (5, '£ 0,05'),
])
def test_money_in_brazilian_format(cents, expected):
    assert money(cents, '£') == expected


@pytest.mark.parametrize(('change', 'expected'), [
    (-0.11165, '-11,2%'),
    (0.085, '+8,5%'),
    (0.0, '0,0%'),
])
def test_percent(change, expected):
    assert percent(change) == expected
