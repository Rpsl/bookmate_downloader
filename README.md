# Bookmate Downloader

Download books as epub from bookmate.com and saves them as epub format files.

## Installation

```bash
git clone https://github.com/Rpsl/bookmate_downloader
cd bookmate_downloader
pip install -r requirements.txt
python main.py
```

# You needs to be subscribed to bookmate.com premium!!!

I think it works on Mac OS X only at the moment.

Steps:

1. Buy the subscription at bookmate.com
2. Authorize at bookate.com with your chrome browser
3. install python3
4. Copy the bookid
5. `python3 bookmate_downloader.py --bookid BookIdHere`
6. The epub will be downloaded to "out"

# Broken files

Sometimes, after downloading, some files cannot be read by various programs. Try to open the book in any editor and save again.

- https://github.com/Sigil-Ebook/Sigil - can autofix books when open

Also, you can try use [epubcheck](https://github.com/w3c/epubcheck/)
