import logging
from requests.auth import HTTPBasicAuth
from jira.client import JIRA
from pprint import pformat
from action import Action

class JiraWrapper(object):

    def __init__(self, name, url, username, password, projectKey, issuetypeName, assignee, customFields, action):

        self.name = name
        self.url = url
        self.username = username
        self.password = password
        self.projectKey = projectKey
        self.issuetypeName = issuetypeName
        self.logger = logging.getLogger("rss2jira")
        self.assignee = assignee
        self.customFields = customFields
        self.action = Action( action )

        self.options = {
            'server': url,
            'basic_auth': {
                'username': username,
                'password': password,
            },
        }

        self.jira = JIRA(self.options)
        self._authenticate()

    def _authenticate(self):
        # This is a work around for a reported bug reguarding basic auth:
        # https://bitbucket.org/bspeakmon/jira-python/pull-request/4/fix-for-issue-6-basic-authentication
        # https://bitbucket.org/bspeakmon/jira-python/issue/6/basic-authentication-doesnt-actually-use
        auth_url = self.url + '/rest/auth/1/session'
        auth_data = HTTPBasicAuth(self.username, self.password)
        rv = self.jira._session.get(auth_url, auth=auth_data)
        self.logger.info("Authentication result: {} {}".format(rv.status_code, rv.text))

    def _issue_dict(self, entry):
        resolvedFields = self._resolve_action( entry )
        return dict(
                {'project': {'key': self.projectKey},
                    'summary': entry.title,
                    'description': "Go to {} ({}).".format(self.name, entry.link) + "\r\n\r\n" + self.action.result,
                    'issuetype': {'name': self.issuetypeName},
                    'assignee': {'name': entry.assignee if hasattr(entry, "assignee") else self.assignee}},
                **resolvedFields)

    def _resolve_action( self, entry ):
        try:
            return self.action.apply( entry.link, self.customFields )
        except Exception as e:
            self.logger.exception( "Link : " + entry.link + ", with JIRA data: " + str(self.customFields) )
            raise e

    def create_issue(self, entry):
        fields = self._issue_dict(entry)
        try:
            return self.jira.create_issue(fields=fields)
        except Exception as ex:
            self.logger.info("Caught exception while creating JIRA issue. " +
                "Reauthenticating and trying again... %s", ex)
            self._authenticate()
            return self.jira.create_issue(fields=fields)
