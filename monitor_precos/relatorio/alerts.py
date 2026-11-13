"""Os alertas: produtos cujo preço subiu ou caiu além do limite desde a
coleta anterior."""

from monitor_precos.armazenamento.history import PriceRow
from monitor_precos.text import plural


def find_alerts(rows: list[PriceRow], threshold: float) -> list[PriceRow]:
    """threshold em porcentagem: 5 quer dizer 5%. A maior variação vem
    primeiro."""
    # A folga evita que 5% exatos virem 4,9999...% na conta com float.
    alerts = [row for row in rows if row.change is not None
              and abs(row.change) * 100 >= threshold - 1e-9]
    return sorted(alerts, key=lambda row: abs(row.change), reverse=True)


def threshold_text(threshold: float) -> str:
    return f'{threshold:g}%'.replace('.', ',')


def summary(rows: list[PriceRow], alerts: list[PriceRow],
            threshold: float) -> str:
    collected = sum(1 for row in rows if row.error is None)
    return ' · '.join([
        plural(collected, 'produto coletado', 'produtos coletados'),
        plural(len(alerts), 'alerta', 'alertas')
        + f' (variação de {threshold_text(threshold)} ou mais)',
        plural(len(rows) - collected, 'problema', 'problemas'),
    ])
