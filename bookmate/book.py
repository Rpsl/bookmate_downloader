import array
import base64
import logging
from bookmate.parser import ScriptParser
from Crypto.Cipher import AES
from xml.etree import ElementTree as ET


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

    @property
    def title(self):
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

    def human_name(self):
        return self.downloader.human_name(self.title)

    def autofix(self):
        return self.downloader.autofix()


def bytess(arr):
    assert type(arr) in [list]
    return array.array('B', arr).tobytes()
