import logging
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from datetime import date
from reutil import remap
import copy
import unicodedata


class Action(object):
    def __init__(self, definitions):
        self.logger = logging.getLogger('rss2jira')
        if definitions is None:
            self.disabled = True
            return
        self.definitionTemplates = definitions

    def apply(self, data, jiraData):
        self.jiraData = copy.deepcopy(jiraData)
        self.variables = dict()
        self.links = set()
        self.result = ""
        if not hasattr(self, "disabled"):
            self.definitions = copy.deepcopy(self.definitionTemplates)
            for definition in self.definitions:
                try:
                    self._apply(data, definition)
                except Exception as e:
                    self.logger.exception("Exception encountered processing action " + str(definition) + "\r\nException: {}".format(e))
                    raise e
        return self.jiraData

    def _apply(self, data, definition):
        action = definition["type"]
        self.logger.debug("Performing action _{}".format(action))
        try:
            output = getattr(self, '_{}'.format(action))(data, definition)
            if "outputActions" not in definition:
                self.logger.debug("No output actions found under _" + action)
                return
            for outputAction in definition["outputActions"]:
                self._apply(output, outputAction)
        except Exception as e:
            # self.logger.exception("Exception caught in action: " + str(definition) + "\r\nException: {}".format(e))
            if "exceptActions" in definition:
                self.logger.debug("Error in " + action+ ", except action found.")
                for exceptAction in definition["exceptActions"]:
                    self._apply(data, exceptAction)
            else:
                raise e

    def _update(self):
        self.logger.debug("Updating dictionaries. Variables: " + str(self.variables))
        for varKey, varVal in self.variables.items():
            p = re.compile("{{\s*" + varKey + "\s*}}")
            self._replaceDeleteNone = True
            self._replaceDict(p, varVal, self.jiraData)
            self._replaceDeleteNone = False
            self._replaceList(p, varVal, self.definitions)

    def _updateVal(self, var, val):
        self.logger.debug("Updating dictionaries. Variable: " + var + "=" + str(val))
        p = re.compile("{{\s*" + var + "\s*}}")
        self._replaceDeleteNone = True
        self._replaceDict(p, val, self.jiraData)
        self._replaceDeleteNone = False
        self._replaceList(p, val, self.definitions)

    def _replaceDict(self, p, replace, dictionary):
        for key, val in dictionary.items():
            if p.match(key) is not None:
                del dictionary[key]
                key = p.sub(replace, key)
            replaced = self._replaceType(p, replace, val)
            if key is not None and (replaced is not None or val is None):
                dictionary[key] = replaced
            elif replaced is None and val is not None and self._replaceDeleteNone:
                del dictionary[key]
        return dictionary

    def _replaceType(self, p, replace, obj):
        if obj is None or isinstance(obj, bool) or isinstance(obj, int) or isinstance(obj, float):
            return obj
        elif isinstance(obj, str):
            if len(p.sub("", obj)) < len(obj):
                self.logger.debug("Replacing string: " + obj + ". Length of unaltered text: " + str(len(p.sub("", obj))))
            if len(obj) > 0 and len(p.sub("", obj)) == 0:
                return replace
            return p.sub(str(replace), obj)
        elif isinstance(obj, dict):
            return self._replaceDict(p, replace, obj)
        elif isinstance(obj, list):
            return self._replaceList(p, replace, obj)
        elif not isinstance(obj, str):
            raise ValueError("What type is this? " + str(type(obj)) + "=" + str(obj))


    def _replaceList(self, p, replace, _list):
        for idx, item in enumerate(_list):
            val = self._replaceType(p, replace, item)
            if val is None:
                del _list[idx]
            else:
                replaced = self._replaceType(p, replace, item)
                if replaced != _list[idx]:
                    self.logger.debug("Replaced list item " + _list[idx] + " with " + replaced)
                    _list[idx] = replaced
        return _list

    def _follow(self, data, definition):
        if not hasattr(self, "session"):
            self.session = requests.Session()
        url = definition["url"] if "url" in definition else data
        self.logger.debug("Performing _{}".format(definition['method']) + ": " + str(url))
        output = self._getBody(getattr(self, '_{}'.format(definition['method']))(url, definition))
        return output

    def _getBody(self, response):
        if isinstance(response, requests.models.Response):
            return response.content.decode('utf-8', errors="ignore")
        if isinstance(response, list):
            return '[%s]' % ', '.join(map(str, response))
        if isinstance(response, str):
            return response

    def _get(self, url, definition):
        return self.session.get(url, **definition['kwargs'])

    def _post(self, url, definition):
        return self.session.post(url, **definition['kwargs'])

    def _float(self, data, definition):
        self.logger.debug("floating data: " + str(data))
        return float(data)

    def _register(self, data, definition):
        val = definition["val"] if "val" in definition else unicodedata.normalize('NFKD', data).encode('ascii','ignore') if isinstance( data, unicode ) else data
        self.variables[definition["var"]] = val
        self._update()

    def _re(self, data, definition):
        if "replace" in definition:
            p = re.compile(definition["find"], re.DOTALL)
            self.logger.debug("Performing regex replace")
            return p.sub(definition["replace"], data)
        self.logger.debug("Performing regex search")
        p = re.compile(definition["find"])
        if "each" in definition:
            self.logger.debug("Iterating over regex results")
            results = re.findall(p, data)
            for action in definition["each"]:
                for result in results:
                    self.logger.debug("Action: " + str(action) + ",Result: " + result)
                    self._apply(result, action)
            return None
        result = p.search(data)
        if result is None:
            if "default" in definition:
                self.logger.debug("No result found. Returning default: " + str(definition["default"]))
                return definition["default"]
            else:
                self.logger.debug("No result found")
                return None
        return result.group(definition["group"])

    def _resultAppend(self, data, definition):
        self.logger.debug("Appending result: " + str(len(data)) + " characters")
        self.result += data

    def _soup(self, data, definition):
        soup = BeautifulSoup(data, "html.parser")
        #self.logger.debug("Soup: " + soup.prettify())
        self.logger.debug("Soup definition: " + str(definition))
        return soup.find(definition["element"], **definition["kwargs"]).get_text()

    def _str(self, data, definition):
        return str(data)

    def _pass(self, data, definition):
        pass

    def _now(self, data, definition):
        return datetime.now()

    def _today(self, data, definition):
        return date.today()

    def _remap(self, data, definition):
        return remap(data, definition["map"])

    def _getattr(self, data, definition):
        return getattr(data, definition["name"], definition["default"]) if "default" in definition else getattr(data, definition["name"])

    def _set(self, data, definition):
        name = definition["name"];
        if name not in self.variables:
            self.variables[name] = set()
        self.variables[name].add(data)

    def _iter(self, data, definition):
        name = definition["name"]
        if name in self.variables:
            for val in self.variables[name]:
                for action in definition["each"]:
                    self._apply(val, action)

    def _link(self, data, definition):
        self.links.add(re.sub("[\)>\"']", "", data))

    def _filterLines(self, data, definition):
        match = re.compile(definition["match"]) if "match" in definition else None
        notMatch = re.compile(definition["notMatch"]) if "notMatch" in definition else None
        lines = data.splitlines()
        result = []
        for line in lines:
            if match is not None and match.search(line) or notMatch is not None and not notMatch.search(line):
                result.append(line)
        return "\r\n".join(result)
