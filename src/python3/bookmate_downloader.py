#!/usr/bin/env python

# todo fix imports
# is craphack https://stackoverflow.com/questions/19623267/importerror-no-module-named-crypto-cipher/21116128#21116128
import sys

try:
    import crypto

    sys.modules['Crypto'] = crypto
except ImportError:
    pass

import os
import argparse
import subprocess
import sys
from xml.etree import ElementTree as ET
import shutil
import json
import array
import base64
import zipfile
from Crypto.Cipher import AES
import logging
from pycookiecheat import chrome_cookies
from sqlite3 import OperationalError
import requests
from html.parser import HTMLParser


def bytess(arr):
    assert type(arr) in [list]
    return array.array('B', arr).tobytes()


def zipdir(path, ziph):
    # ziph is zipfile handle
    top = path
    for root, dirs, files in os.walk(path):
        for file in files:
            src = os.path.join(root, file)
            ziph.write(filename=src, arcname=os.path.relpath(src, top))


class ScriptParser(HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__data = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.__data = ""

    def handle_endtag(self, tag):
        if tag == "script":
            self.handle_script_data(self.__data)
            self.__data = None

    def handle_data(self, data):
        if self.__data is not None:
            self.__data += data

    def handle_script_data(self, script_data):
        logging.debug("script_data:%s ...", script_data[:40])
        S = "window.CLIENT_PARAMS"
        if S not in script_data:
            return
        after = script_data[script_data.find(S) + len(S):]
        logging.debug("after: %s", after)
        json_text = after[after.find("=") + 1:after.find(";")]
        self.client_params = json.loads(json_text.strip())
        logging.debug("client_params: %s", self.client_params)


class Downloader:
    def __init__(self, outdir, cookies):
        self.outdir = outdir
        self.cookies = cookies

    def save_bytes(self, bts, name):
        fpath = os.path.join(self.outdir, name)
        dirpath = os.path.dirname(fpath)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        fout = open(fpath, "wb")
        fout.write(bts)
        fout.close()

    def request_url(self, url):
        logging.debug("downloading %s ..." % url)
        response = requests.get(url, cookies=self.cookies)
        logging.debug("response:%s", response)
        assert response.status_code in [200], response.status_code
        return response

    def path(self, sub):
        return os.path.join(self.outdir, sub)

    def delete_downloaded(self):
        shutil.rmtree(self.outdir)

    def delete_css(self):
        for root, dirs, files in os.walk(".", topdown=False):
            for name in files:
                if name.lower().endswith(".css"):
                    f = open(os.path.join(root, name), "w")
                    f.write("")
                    f.close()

    def make_epub(self):
        assert os.path.exists(self.outdir), self.outdir
        epubfpath = self.outdir + ".epub"
        zipf = zipfile.ZipFile(epubfpath, 'w', zipfile.ZIP_DEFLATED)
        zipdir(self.outdir, zipf)
        zipf.close()
        return epubfpath

    def human_name(self, outdir, title):
        file_name = outdir + "/" + title + ".epub"
        os.rename(self.outdir + ".epub", file_name)
        return file_name

    def autofix(self, outdir, file_path):
        tmp_file = outdir + '/tmp.epub'

        try:
            ebook = subprocess.check_output(['which', 'ebook-convert'])
            ebook = ebook.strip(b'\n')
        except subprocess.CalledProcessError:
            logging.error("ebook-convert not found in system. it's are part of Calibre application, try to install its")
            return False

        try:
            subprocess.check_call([ebook, os.path.abspath(file_path), os.path.abspath(tmp_file)], shell=False,
                                  stdout=subprocess.DEVNULL)
            os.unlink(file_path)
            os.rename(tmp_file, file_path)
        except subprocess.CalledProcessError:
            logging.error(
                "Autofix finished with error. Try manualy call autofix: `which ebook-convert` input_file output_file")


class BookDownloader:
    def __init__(self, bookid, downloader, secret=None):
        self.bookid = bookid
        self.downloader = downloader
        self.secret = self.download_secret() if secret is None else secret
        assert self.secret is not None

    def download_secret(self):
        url = "https://reader.bookmate.com/%s" % self.bookid
        html = self.downloader.request_url(url).text
        logging.debug("html:%s ...", html[:20])
        parser = ScriptParser()
        parser.feed(html)
        secret = parser.client_params["secret"]
        logging.debug("secret: %s", secret)
        return secret

    def download(self):
        encrypted_metadata = self.download_metadata(self.bookid)
        metadata = self.decrypt_metadata(encrypted_metadata, self.secret)
        self.process_metadata(metadata)

    def download_metadata(self, bookid):
        url = "https://reader.bookmate.com/p/api/v5/books/%s/metadata/v4" % bookid  # noqa: E501
        metadata_response = self.downloader.request_url(url)
        logging.debug("metadata_response:%s ...", metadata_response.text[:40])
        return metadata_response.json()

    def decrypt_metadata(self, encrypted_metadata, secret):
        assert type(encrypted_metadata) in [dict]
        metadata = {}
        for (key, val) in encrypted_metadata.items():
            if type(val) in [list]:
                metadata[key] = self.decrypt(secret, bytess(val))
            else:
                metadata[key] = val
        return metadata

    def decrypt(self, secret, data):
        assert type(secret) in [str], type(secret)
        key = base64.b64decode(secret)
        bts = self.rawDecryptBytes(data[16:], key, data[:16])
        logging.debug("len(bts):%s", len(bts))
        logging.debug("lastbyte:%s", bts[-1])
        padsize = -1 * bts[-1]
        return bts[:padsize]

    def rawDecryptBytes(self, cryptArr, key, iv):
        assert type(cryptArr) in [bytes]
        assert type(key) in [bytes]
        assert type(iv) in [bytes]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.decrypt(cryptArr)

    def process_metadata(self, metadata):
        self.downloader.save_bytes(b"application/epub+zip", "mimetype")
        self.downloader.save_bytes(metadata["container"], "META-INF/container.xml")  # noqa: E501
        self.downloader.save_bytes(metadata["opf"], "OEBPS/content.opf")
        self.process_opf(metadata["document_uuid"])
        self.downloader.save_bytes(metadata["ncx"], "OEBPS/toc.ncx")

    def process_opf(self, uuid):
        content_file = self.downloader.path("OEBPS/content.opf")
        for event, elem in ET.iterparse(content_file, events=["start"]):
            if event != 'start':
                continue
            if not elem.tag.endswith("}item"):
                continue
            if "href" not in elem.attrib:
                continue
            fname = elem.attrib["href"]
            if fname == "toc.ncx":
                continue
            logging.debug("fname:%s", fname)
            url = "https://reader.bookmate.com/p/a/4/d/{uuid}/contents/OEBPS/{fname}".format(uuid=uuid, fname=fname)
            response = self.downloader.request_url(url)
            self.downloader.save_bytes(response.content, "OEBPS/" + fname)

    def extract_title(self):
        namespace = {
            'ncx': "http://www.daisy.org/z3986/2005/ncx/"
        }
        root = ET.parse(self.downloader.path("OEBPS/toc.ncx"))
        return root.find('./ncx:docTitle/ncx:text', namespace).text

    def delete_downloaded(self):
        self.downloader.delete_downloaded()

    def make_epub(self):
        return self.downloader.make_epub()

    def delete_css(self):
        self.downloader.delete_css()

    def human_name(self, outdir):
        return self.downloader.human_name(outdir, self.extract_title())

    def autofix(self, outdir, file_path):
        return self.downloader.autofix(outdir, file_path)


class Bookmate:
    def __init__(self, outdir, cookies):
        assert os.path.exists(outdir), "path %s does not exist" % outdir
        self.outdir = outdir
        assert cookies
        self.cookies = cookies

    def get_book(self, bookid):
        outdir = os.path.join(self.outdir, bookid)
        downloader = Downloader(outdir=outdir, cookies=self.cookies)
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

    file = None

    if arg.download:
        book.download()
    if arg.delete_css:
        book.delete_css()
    if arg.make_epub:
        file = book.make_epub()
    if arg.human_name:
        file = book.human_name(arg.outdir)
    if arg.delete_downloaded:
        book.delete_downloaded()
    if arg.autofix and file is not None:
        book.autofix(arg.outdir, file)

    # url = bookid if arg.bookid.startswith("http") else "https://reader.bookmate.com/%s" % arg.bookid  # noqa: E501
    # downloader = BookDownloader(url, "out")
    # downloader.download_book()
    # downloader.make_epub()
    # downloader.delete_downloaded()
