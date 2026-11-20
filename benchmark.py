import argparse
import sys
from http.client import HTTPException
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


REQUESTS = 10
CHUNK_SIZE = 64 * 1024
TIMEOUT_SECONDS = 30


def download(url: str) -> int:
    request = Request(url, headers={"Accept-Encoding": "identity"})
    received = 0
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        while chunk := response.read(CHUNK_SIZE):
            received += len(chunk)

        # A fixed-length response can reach EOF early without read(size) raising.
        length = response.headers.get("Content-Length")
        if length is not None and not response.headers.get("Transfer-Encoding"):
            if received != int(length):
                raise ValueError(f"неполный ответ: получено {received} из {length} байт")
    return received


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Измерить скорость скачивания по HTTP(S).")
    parser.add_argument("url", help="полный URL файла")
    args = parser.parse_args(argv)
    try:
        target = urlsplit(args.url)
        if target.scheme not in ("http", "https") or not target.hostname:
            parser.error("укажите полный URL с http:// или https://")
    except ValueError as error:
        parser.error(str(error))

    total_bytes = 0
    total_seconds = 0.0
    for number in range(1, REQUESTS + 1):
        start = perf_counter()
        try:
            size = download(args.url)
        except (OSError, HTTPException, ValueError) as error:
            print(f"Запрос {number}/{REQUESTS}: {error}", file=sys.stderr)
            return 1
        total_seconds += perf_counter() - start
        total_bytes += size

    print(f"Завершено запросов: {REQUESTS}")
    print(f"Среднее время запроса: {total_seconds * 1000 / REQUESTS:.2f} мс")
    print(f"Скачано всего: {total_bytes} байт")
    print(f"Скорость скачивания: {total_bytes * 8 / total_seconds / 1_000_000:.3f} Мбит/с")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
