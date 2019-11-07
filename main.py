#!/usr/bin/env python
try:
    import sys
    import crypto

    # https://stackoverflow.com/questions/19623267/importerror-no-module-named-crypto-cipher/21116128#21116128
    sys.modules['Crypto'] = crypto
except ImportError:
    pass

import os
import logging
import argparse
from pycookiecheat import chrome_cookies
from sqlite3 import OperationalError
from bookmate.downloader import Downloader
from bookmate.book import BookDownloader


class Bookmate:
    def __init__(self, outdir, cookies):
        assert os.path.exists(outdir), "path %s does not exist" % outdir
        self.outdir = outdir
        assert cookies
        self.cookies = cookies

    def get_bookidr(self, bookid):
        return os.path.join(self.outdir, bookid)

    def get_book(self, bookid):
        downloader = Downloader(
            outdir=self.outdir,
            bookdir=self.get_bookidr(bookid),
            cookies=self.cookies
        )
        return BookDownloader(bookid=bookid, downloader=downloader)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bookid", help="bookid, take from the book url", required=True)
    parser.add_argument("--outdir", help="Output directory", default="out")
    parser.add_argument("--log", help="loglevel", type=lambda name: logging._nameToLevel[name], default="INFO",
                        choices=logging._nameToLevel.values())
    parser.add_argument("--download", type=bool, default=True)
    parser.add_argument("--delete_downloaded", type=bool, default=True)
    parser.add_argument("--make_epub", type=bool, default=True)
    parser.add_argument("--delete_css", type=bool, default=True)
    parser.add_argument("--cookies", help="Path to the Google Chrome cookies database")
    parser.add_argument("--human-name", help="Save book with original title", action='store_true')
    parser.add_argument("--autofix", help="Try autofix epub", action='store_true')

    arg = parser.parse_args()

    logformat = '%(asctime)s (%(name)s) %(levelname)s %(module)s.%(funcName)s():%(lineno)d  %(message)s'  # noqa: E501
    logging.basicConfig(level=arg.log, format=logformat)

    if not os.path.exists(arg.outdir):
        logging.info("Creating folder %s ..." % arg.outdir)
        os.makedirs(arg.outdir)

    try:
        cookies = chrome_cookies("https://reader.bookmate.com", arg.cookies)
    except OperationalError:
        sys.exit("Can't open default cookies database.\nTry use argument --cookies with path to cookies database")

    bookmate = Bookmate(outdir=arg.outdir, cookies=cookies)
    book = bookmate.get_book(bookid=arg.bookid)

    if arg.download:
        book.download()
    if arg.delete_css:
        book.delete_css()
    if arg.make_epub:
        book.make_epub()
    if arg.autofix:
        book.autofix()
    if arg.human_name:
        book.human_name()
    if arg.delete_downloaded:
        book.delete_downloaded()

    # url = bookid if arg.bookid.startswith("http") else "https://reader.bookmate.com/%s" % arg.bookid  # noqa: E501
    # downloader = BookDownloader(url, "out")
    # downloader.download_book()
    # downloader.make_epub()
    # downloader.delete_downloaded()
