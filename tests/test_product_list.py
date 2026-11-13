import pytest

from monitor_precos.coleta.product_list import (
    ProductListError,
    read_product_urls,
)

URL_A = 'https://books.toscrape.com/catalogue/a/index.html'
URL_B = 'https://books.toscrape.com/catalogue/b/index.html'


def write(tmp_path, text, encoding='utf-8'):
    path = tmp_path / 'produtos.csv'
    path.write_bytes(text.encode(encoding))
    return path


def test_reads_one_url_per_line(tmp_path):
    path = write(tmp_path, f'url\n{URL_A}\n{URL_B}\n')

    assert read_product_urls(path) == [URL_A, URL_B]


def test_skips_blank_lines_comments_and_repeated_urls(tmp_path):
    path = write(tmp_path, f'URL\n\n# concorrente A\n{URL_A}\n  {URL_A}  \n'
                           f'{URL_B}\n')

    assert read_product_urls(path) == [URL_A, URL_B]


def test_other_columns_are_allowed(tmp_path):
    # Quem mantém a lista no Excel costuma pôr uma coluna com o apelido.
    path = write(tmp_path, f'apelido;url\nLivro A;{URL_A}\n')

    assert read_product_urls(path) == [URL_A]


def test_reads_the_csv_saved_by_excel(tmp_path):
    # Excel em português: ponto e vírgula, acentos em cp1252 ou UTF-8 com
    # BOM.
    cp1252 = write(tmp_path, f'Produto;URL\nCaneca Térmica;{URL_A}\n',
                   encoding='cp1252')
    assert read_product_urls(cp1252) == [URL_A]

    bom = write(tmp_path, f'url\n{URL_B}\n', encoding='utf-8-sig')
    assert read_product_urls(bom) == [URL_B]


def test_missing_file(tmp_path):
    with pytest.raises(ProductListError, match='Não encontrei a lista'):
        read_product_urls(tmp_path / 'produtos.csv')


def test_needs_a_url_column(tmp_path):
    path = write(tmp_path, f'link\n{URL_A}\n')

    with pytest.raises(ProductListError, match='coluna "url"'):
        read_product_urls(path)


def test_invalid_address_says_the_line(tmp_path):
    path = write(tmp_path, f'url\n{URL_A}\nbooks.toscrape.com/x\n')

    with pytest.raises(ProductListError) as error:
        read_product_urls(path)

    assert str(error.value) == (
        'Linha 3 do produtos.csv: "books.toscrape.com/x" não é um endereço '
        'de página (precisa começar com http:// ou https://)'
    )


def test_empty_list(tmp_path):
    path = write(tmp_path, 'url\n\n# nada aqui ainda\n')

    with pytest.raises(ProductListError, match='não tem nenhum produto'):
        read_product_urls(path)


def test_empty_file(tmp_path):
    path = write(tmp_path, '')

    with pytest.raises(ProductListError, match='coluna "url"'):
        read_product_urls(path)
