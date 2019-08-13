__version__ = '0.1.23'

from rss2jira.trackedentries import Sqlite3TrackedEntries
from rss2jira.binding import BindingFactory
from rss2jira.rssreader import RssReader
from rss2jira.app import MainLoop
from rss2jira.issueFactory import JiraWrapper

import logging

try:
    logging.getLogger('rss2jira').addHandler(logging.NullHandler())
except AttributeError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    logging.getLogger('rss2jira').addHandler(NullHandler())
