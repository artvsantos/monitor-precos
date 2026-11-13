"""Lê a lista de produtos a monitorar: um CSV com a coluna "url"."""

import csv
import io
from pathlib import Path
from urllib.parse import urlsplit


class ProductListError(Exception):
    """Problema na lista de produtos. A mensagem é para quem usa."""


def read_product_urls(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise ProductListError(
            f'Não encontrei a lista de produtos: {path}',
        ) from None
    # O Excel em português salva CSV em cp1252 ou em UTF-8 com BOM, e com
    # ponto e vírgula entre as colunas.
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252')
    header = text.split('\n', 1)[0]
    reader = csv.reader(io.StringIO(text),
                        delimiter=';' if ';' in header else ',')
    columns = [name.strip().lower() for name in next(reader, [])]
    if 'url' not in columns:
        raise ProductListError(
            f'A lista {path.name} precisa de uma coluna "url" na primeira '
            'linha, com um endereço de produto por linha embaixo',
        )
    position = columns.index('url')

    urls = []
    for row in reader:
        if not any(cell.strip() for cell in row) or row[0].startswith('#'):
            continue  # linha em branco ou comentário
        url = row[position].strip() if position < len(row) else ''
        address = urlsplit(url)
        if address.scheme not in ('http', 'https') or not address.netloc:
            raise ProductListError(
                f'Linha {reader.line_num} do {path.name}: "{url}" não é um '
                'endereço de página (precisa começar com http:// ou '
                'https://)',
            )
        if url not in urls:
            urls.append(url)
    if not urls:
        raise ProductListError(
            f'A lista {path.name} não tem nenhum produto. Coloque um '
            'endereço por linha, na coluna "url".',
        )
    return urls
