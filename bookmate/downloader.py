import os
import shutil
import logging
import subprocess
import zipfile
import requests


class Downloader:
    def __init__(self, outdir, bookdir, cookies):
        self.outdir = outdir
        self.bookdir = bookdir
        self.cookies = cookies

    def save_bytes(self, bts, name):
        fpath = os.path.join(self.bookdir, name)
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
        return os.path.join(self.bookdir, sub)

    def delete_downloaded(self):
        shutil.rmtree(self.bookdir)

    def delete_css(self):
        for root, dirs, files in os.walk(".", topdown=False):
            for name in files:
                if name.lower().endswith(".css"):
                    f = open(os.path.join(root, name), "w")
                    f.write("")
                    f.close()

    def make_epub(self):
        assert os.path.exists(self.bookdir), self.bookdir
        epubfpath = self.bookdir + ".epub"
        zipf = zipfile.ZipFile(epubfpath, 'w', zipfile.ZIP_DEFLATED)
        zip_dir(self.bookdir, zipf)
        zipf.close()
        return epubfpath

    def human_name(self, title):
        human_name = "{}/{}.epub".format(self.outdir, title)
        os.rename("{}.epub".format(self.bookdir), human_name)
        return human_name

    def autofix(self):
        book_file = "{}.epub".format(self.bookdir)
        temp_file = "{}/temporary.epub".format(self.outdir)

        try:
            ebook = subprocess.check_output(['which', 'ebook-convert'])
            ebook = ebook.strip(b'\n')
        except subprocess.CalledProcessError:
            logging.error("ebook-convert not found in system. it's are part of Calibre application, try to install its")
            return False

        try:
            subprocess.check_call([ebook, os.path.abspath(book_file), os.path.abspath(temp_file)], shell=False,
                                  stdout=subprocess.DEVNULL)
            os.unlink(book_file)
            os.rename(temp_file, book_file)
        except subprocess.CalledProcessError:
            logging.error(
                "Autofix finished with error. Try manualy call autofix: `which ebook-convert` input_file output_file")


def zip_dir(path, ziph):
    # zip_dir is zipfile handle
    top = path
    for root, dirs, files in os.walk(path):
        for file in files:
            src = os.path.join(root, file)
            ziph.write(filename=src, arcname=os.path.relpath(src, top))
