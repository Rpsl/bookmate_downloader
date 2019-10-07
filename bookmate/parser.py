import json
import logging
from html.parser import HTMLParser


class ScriptParser(HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_params = None
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
