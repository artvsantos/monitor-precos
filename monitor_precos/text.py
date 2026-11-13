"""Números do jeito brasileiro: 1.234,56 e 8,5%."""


def plural(count: int, singular: str, plural_form: str) -> str:
    number = f'{count:,}'.replace(',', '.')
    return f'{number} {singular if count == 1 else plural_form}'


def money(cents: int, currency: str) -> str:
    amount = f'{cents / 100:,.2f}'  # 1,234.50
    return f'{currency} ' + amount.translate(str.maketrans(',.', '.,'))


def percent(change: float) -> str:
    """change em fração: -0.112 vira "-11,2%"."""
    if change == 0:
        return '0,0%'
    return f'{change * 100:+.1f}%'.replace('.', ',')
