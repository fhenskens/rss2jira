import logging
import requests
import re
from bs4 import BeautifulSoup

class Action(object):
    def __init__(self, definition):
        self.logger = logging.getLogger('rss2jira')
        if definition is None:
            self.disabled = True
            return
        self.definitionTemplate = definition

    def apply(self, data, jiraData):
        self.jiraData = dict(jiraData)
        self.variables = dict()
        self.result = ""
        if not hasattr(self, "disabled"):
            self.definition = dict(self.definitionTemplate)
            self._apply(data, self.definition)
        return self.jiraData

    def _apply(self, data, definition):
        action = definition["type"]
        params = definition["params"] if "params" in definition else None
        self.logger.debug("Performing action _{}".format(action))
        try:
            output = getattr(self, '_{}'.format(action))(data, params)
            if "outputActions" not in definition:
                self.logger.debug("No output actions found under " + action)
                return
            for outputAction in definition["outputActions"]:
                self._apply(output, outputAction)
        except Exception as e:
            self.logger.debug("Exception caught in action: " + str(definition))
            if "exceptActions" in definition:
                self.logger.debug("Except action found.")
                for exceptAction in definition["exceptActions"]:
                    self._apply(data, exceptAction)
            else:
                self.logger.exception("Exception encountered processing action " + str(definition))
                raise e

    def _update(self):
        self.logger.debug("Updating dictionaries. Variables: " + str(self.variables))
        for varKey, varVal in self.variables.items():
            p = re.compile("{{\s*" + varKey + "\s*}}")
            self._replaceDict(p, varVal, self.jiraData)
            self._replaceDict(p, varVal, self.definition)

    def _updateVal(self, var, val):
        self.logger.debug("Updating dictionaries. Variable: " + var + "=" + str(val))
        p = re.compile("{{\s*" + var + "\s*}}")
        self._replaceDict(p, val, self.jiraData)
        self._replaceDict(p, val, self.definition)

    def _replaceDict(self, p, replace, dictionary):
        for key, val in dictionary.items():
            if p.match(key) is not None:
                del dictionary[key]
                key = p.sub(replace, key)
            dictionary[key] = self._replaceType(p, replace, val)
        return dictionary

    def _replaceType(self, p, replace, obj):
        if obj is None or isinstance(obj, bool) or isinstance(obj, int) or isinstance(obj, float):
            return obj
        elif isinstance(obj, str):
            if len(p.sub("", obj)) < len(obj):
                self.logger.debug("Replacing string: " + obj + ". Length of unaltered text: " + str(len(p.sub("", obj))))
            if not isinstance(replace, str) and len(obj) > 0 and len(p.sub("", obj)) == 0:
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
            _list[idx] = self._replaceType(p, replace, item)
        return _list

    def _follow(self, data, params):
        if not hasattr(self, "session"):
            self.session = requests.Session()
        self.logger.debug("Performing _{}".format(params['method']))
        output = self._getBody(getattr(self, '_{}'.format(params['method']))(data, params))
        return output

    def _getBody(self, response):
        if isinstance(response, requests.models.Response):
            return response.content.decode('utf-8', errors="ignore")
        if isinstance(response, list):
            return '[%s]' % ', '.join(map(str, response))
        if isinstance(response, str):
            return response

    def _get(self, url, params):
        return self.session.get(url, **params['kwargs'])

    def _post(self, url, params):
        return self.session.post(url, **params['kwargs'])

    def _float(self, data, params):
        return float(data)

    def _register(self, data, params):
        val = params["val"] if "val" in params else data
        self.variables[params["var"]] = val
        self._update()
        self.logger.debug("Post-update:\r\nJira:" + str(self.jiraData) + "\r\nDefinition:" + str(self.definition))

    def _re(self, data, params):
        p = re.compile(params["find"], re.DOTALL)
        return p.sub(params["replace"], data)

    def _resultAppend(self, data, params):
        self.result += data

    def _soup(self, data, params):
        soup = BeautifulSoup(data, "html.parser")
        self.logger.debug("Soup: " + soup.prettify())
        self.logger.debug("Soup Params: " + str(params))
        return soup.find(params["element"], **params["kwargs"]).get_text()

    def _pass(self, data, params):
        pass
