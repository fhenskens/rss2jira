import feedparser
import logging
import urllib2
import socket
import re
from rss2jira.reutil import remap

def validate_feed(feed):
    # We're being a bit permissive; so long as the feed got entries we
    # ignore errors. However, if there are no entries AND feedparser's
    # "bozo" bit is set we throw the "bozo_exception".
    # The reason for being lax is that some of the sources we care about
    # generate errors for slightly non-conformant xml.
    if len(feed.entries) == 0 and feed.bozo:
        raise feed.bozo_exception

    return feed


class RssReader(object):
    def __init__(self, feed_url, keywords=[".*"], timeout=None):
        self.feed_url = feed_url
        self.keywords = keywords
        self.logger = logging.getLogger("rss2jira")
        self.timeout = timeout
        self.consecutive_failures = 0

    def _fetch_all_entries(self):
        try:
            print("connecting to: " + self.feed_url)
            request = urllib2.Request(self.feed_url)
            request.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0")
            opener = urllib2.build_opener()
            stream = opener.open(request, timeout=self.timeout)
            feed = validate_feed(feedparser.parse(stream))
            self.consecutive_failures = 0
            return feed.entries
        except Exception as ex:
            self.consecutive_failures += 1
            self.logger.exception("Failed to fetch from url {}".format(
                    self.feed_url))
            raise

    def get_entries(self):
        entries = []
        for e in self._fetch_all_entries():
            if not hasattr(e, 'title') or len(e.title) == 0:
                e.title = 'No Title'
            if self._keyword_match(e):
                self.logger.debug("Keyword matched.")
                entries.append(e)
            else:
                self.logger.info('Entry does not match keywords, ' +
                    'skipping ({})'.format(e.title.encode('ascii', 'replace')))
        return entries

    def _keyword_match(self, feedEntry):
        plainStrings = []
        for keywordEntry in self.keywords:
            if isinstance(keywordEntry, str):
                plainStrings.append(keywordEntry)
            else:
                # Dictionary keyword definitions should override plainstring keywords
                plainStrings = []
                break
        if len(plainStrings) > 0:
            regex = "|".join(plainStrings)
            self.logger.debug("Plain text match on: " + regex)
            return re.compile(regex, re.IGNORECASE).search(str(feedEntry)) is not None
        for idx, keyword in enumerate(self.keywords):
            if not isinstance(keyword, dict):
                del self.keywords[idx]
        assignee = remap(feedEntry.title, self.keywords)
        self.logger.debug("Remap result for (" + feedEntry.title + "): " + str(assignee))
        if assignee == None:
            return False
        else:
            feedEntry.assignee = assignee
            return True
