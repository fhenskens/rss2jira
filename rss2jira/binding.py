import re
import logging
from rssreader import RssReader
import json

class BindingFactory(object):
    def __init__(self, config, tracked_entries, rss_reader_class,
            issue_creator_class):

        self.socket_timeout = config.get("socket_timeout_sec", None)
        self.keywords = config.get("keywords", [".*"])
        self.tracked_entries = tracked_entries
        self.rss_reader_class = rss_reader_class
        self.issue_creator_class = issue_creator_class
        self.jira_url = config.get("jira_url")
        self.jira_username = config.get("jira_username")
        self.jira_password = config.get("jira_password")
        self.jira_projectKey = config.get("jira_projectKey")
        self.jira_issuetypeName = config.get("jira_issuetypeName")
        self.jira_assignee = config.get("jira_assignee")
        self.jira_custom_fields = config.get("jira_custom_fields") if "jira_custom_fields" in config else dict()
        self.action = config.get("action")
        self.email = config.get("email")

    def create(self, config_entry):
        name = config_entry['name']

        config_keywords = config_entry["keywords"] if "keywords" in config_entry else []
        logging.getLogger('rss2jira').debug("Keywords: {} + {} = {}".format(self.keywords, config_keywords, self.keywords + config_keywords))

        rss_reader = self.rss_reader_class(
                feed_url=config_entry['feed_url'],
                keywords=self.keywords + config_keywords,
                timeout=self.socket_timeout)

        issue_creator = self.issue_creator_class(
                name=config_entry['name'],
                url=self.get_config(config_entry, 'jira_url'),
                username=self.get_config(config_entry, 'jira_username'),
                password=self.get_config(config_entry, 'jira_password'),
                projectKey=self.get_config(config_entry, 'jira_projectKey'),
                issuetypeName=self.get_config(config_entry, 'jira_issuetypeName'),
                assignee=self.get_config(config_entry, 'jira_assignee'),
                customFields=self.get_config(config_entry, 'jira_custom_fields'),
                action=self.get_config(config_entry, 'action'))

        storage = self.tracked_entries.source_view(name)

        return Binding(name, rss_reader, issue_creator, storage)

    def get_config(self, config_entry, key):
        return config_entry[key] if key in config_entry else getattr(self, key)

class Binding(object):
    def __init__(self, name, rss_reader, issue_creator, tracked_entries):
        self.name = name
        self.rss_reader = rss_reader
        self.issue_creator = issue_creator
        self.tracked_entries = tracked_entries
        self.logger = logging.getLogger('rss2jira')

    def pump(self):
        self.logger.info("Fetching entries from {}".format(self.name))
        try:
            entries = self.rss_reader.get_entries()
        except Exception as ex:
            self.logger.exception("{} consecutive failure(s) fetching {}".format(
                    self.rss_reader.consecutive_failures, self.name))
            return

        new_entries = []
        for e in entries:
            entryId = self._getId(e)
            if entryId not in self.tracked_entries:
                new_entries.append(e)
            else:
                self.logger.debug('Entry is tracked, skipping. ({})'.format(
                        e.title.encode('ascii', 'replace')))

        self.logger.info("Got {} entries ({} new)".format(len(entries), len(new_entries)))

        for e in new_entries:
            self.issue_creator.create_issue(e)
            self.tracked_entries.add(self._getId(e))
            self.logger.debug('Tracking new entry. ({})'.format(e.title.encode('ascii', 'replace')))
    def _getId(self, entry):
        if hasattr(entry, "id"):
            return entry.id
        return entry.title + "@" + entry.published
