from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    """O que a página do produto mostra."""

    name: str
    # Em centavos, para não perder centavo com conta de número quebrado.
    price_cents: int
    currency: str
    in_stock: bool
    stock: int | None  # quantidade disponível, quando o site informa


@dataclass(frozen=True)
class Observation:
    """O resultado da coleta de um endereço: o produto ou o erro."""

    url: str
    product: Product | None
    error: str | None
