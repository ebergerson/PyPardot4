'''
A demonstration of connecting to Pardot using both
a pardot-only user and the existing api and
using a sf user utilizing the expanding api.

This demonstration requires a configuration file
called `pardot_demo.ini` to supply all of the
instance specific authentication data needed to
run this code in a specific environment.
The format of the file should match the
example `pardot_demo.ini` file provided
in this package.  The file should
be placed in the users home directory,
purposefully outside this repository.
'''
__author__ = 'eb'

import logging
from logging import Logger
from pathlib import Path
from typing import Tuple, Dict, List
from configparser import ConfigParser

import requests

from auth_pardot_api import AuthPardotAPI
from client import PardotAPI
from auth_handler import T as AuthHndlr, TraditionalAuthHandler, OAuthHandler


class PardotAuthenticationDemo(object):

    def __init__(self, config_file: Path, logger: Logger = None) -> None:
        super().__init__()
        self.config_file = config_file
        self.logger = logger
        self.parser = ConfigParser()
        self.parser.read(config_file)


    def run(self):
        # Demonstrate accessing pardot the traditional way using
        # a Pardot-Only user via the existing PyPardot4 api
        self.access_pardot_via_traditional_api()

        # Demonstrate the acturl requrets and responses
        # needed to access pardot using
        # a salesforce user via SSO using OAuth2
        self.access_pardot_via_oauth_using_raw_requests()

        # Demonstrate accessing pardot using
        # a salesforce user via SSO using OAuth2
        # using the AuthPardotAPI sub-class of the existing PardotAPI class
        self.access_pardot_via_oauth_api()


    def access_pardot_via_oauth_using_raw_requests(self):
        """
        Demonstrate the low level request formation needed to retrieve an access token
        from Salesforce and how to use it to access Pardot.
        """
        self.logger and self.logger.info("\tAccess Pardot via SF SSO Using Raw Requests")
        if self.has_sections(["test_data", "salesforce"]):
            access_token, bus_unit_id = self.retrieve_access_token()
            prospects = self.send_pardot_request(access_token, bus_unit_id)
            self.logger and self.logger.info("\t\t...Success")

    def access_pardot_via_traditional_api(self):
        """
         Use the existing PardotAPI to fetch prospect data via a pardot-only user.
         """
        self.logger and self.logger.info("\tAccess Pardot via PardotAPI using Pardot-Only User")
        if self.has_sections(["test_data", "pardot"]):
            auth_handler = self.get_auth_handler("pardot")
            pd = PardotAPI(auth_handler.username, auth_handler.password, auth_handler.userkey)
            pd.authenticate()
            self.query_pardot_api(pd, "pardot")

        self.logger and self.logger.info("\tAccess Pardot via AuthPardotAPI using Pardot-Only User")
        if self.has_sections(["test_data", "pardot"]):
            auth_handler = self.get_auth_handler("pardot")
            pd = AuthPardotAPI(auth_handler, logger=self.logger)
            pd.authenticate()
            self.query_pardot_api(pd, "pardot")

        self.logger and self.logger.info("\tAccess Pardot Sandbox via AuthPardotAPI using Pardot-Only User")
        if self.has_sections(["test_data", "pardot_sandbox"]):
            auth_handler = self.get_auth_handler("pardot_sandbox")
            pd = AuthPardotAPI(auth_handler, logger=self.logger)
            pd.authenticate()
            self.query_pardot_api(pd, "pardot_sandbox")
            self.logger and self.logger.info("\t\t...Success")

    def access_pardot_via_oauth_api(self):
        """
        Use the AuthPardotAPI to fetch prospect data via OAuth2 using a SSO user from Salesforce
        """

        # Accessing a production pardot server using credentials from a production salesforce instance
        self.logger and self.logger.info("\tAccess Pardot via SF SSO")
        if self.has_sections(["test_data", "salesforce"]):
            auth_handler = self.get_auth_handler("salesforce")
            pd = AuthPardotAPI(auth_handler, logger=self.logger)
            self.query_pardot_api(pd, "salesforce")
            self.logger and self.logger.info("\t\t...Success")

        # Accessing a pardot sandbox server using credentials from a salesforce sandbox instance
        # Commented out because I can't test this, we don't have a pardot sandbox
        # self.logger and self.logger.info("\tAccess Pardot Sandbox via SF Sandbox SSO")
        # if self.has_sections(["test_data", "salesforce_sandbox"]):
        #     auth_handler = self.get_auth_handler("salesforce_sandbox")
        #     pd = AuthPardotAPI(auth_handler, logger=self.logger)
        #     self.query_pardot_api(pd, "salesforce_sandbox")
        #     self.logger and self.logger.info("\t\t...Success")

    def query_pardot_api(self, pd: PardotAPI, section: str) -> Tuple[Dict, List]:
        """
        Use a pardot api to fetch prospect data
        The read_by_email() utilizes an http post while the query() utilizes an http get().
        """
        prospect_email = self.parser.get("test_data", "prospect_email")
        response = pd.prospects.read_by_email(email=prospect_email)
        prospect = response["prospect"]
        self.logger and self.logger.info(
            f"\t\tFound Prospect in {section}: {prospect['first_name']} {prospect['last_name']} for email {prospect['email']}")

        prospect_date_filter = self.parser.get("test_data", "prospect_date_filter", fallback="2021-01-01")
        response = pd.prospects.query(created_after=prospect_date_filter)
        prospects = response["prospect"]
        self.logger and self.logger.info(f"\t\tFound {len(prospects)} Prospects in {section} created after {prospect_date_filter}:")
        for p in prospects:
            self.logger and self.logger.debug(f"\t\t\t{p['created_at']}: {p['first_name']} {p['last_name']} <{p['email']}>")

        return prospect, prospects

    def retrieve_access_token(self):
        self.logger and self.logger.debug("\t\tAuthenticate Pardot with with OAuth2 parameters from 'salesforce'")
        auth_handler = self.get_auth_handler("salesforce")
        params = {
            "grant_type": "password",
            "client_id": auth_handler.consumer_key,
            "client_secret": auth_handler.consumer_secret,
            "username": auth_handler.username,
            "password": auth_handler.password + auth_handler.token
        }
        url = "https://login.salesforce.com/services/oauth2/token"
        r = requests.post(url, params=params)
        access_token = r.json().get("access_token")
        instance_url = r.json().get("instance_url")
        self.logger and self.logger.debug(
            f"\t\tRetrieved oauth access_token for {instance_url}")

        return access_token, auth_handler.business_unit_id

    def send_pardot_request(self, access_token, bus_unit_id) -> List:
        prospect_date_filter = self.parser.get("test_data", "prospect_date_filter", fallback="2021-01-01")
        params = {"format": "json",
                  "created_after": prospect_date_filter}
        headers = {"Authorization": f"Bearer {access_token}",
                   "Pardot-Business-Unit-Id": bus_unit_id,
                   "Content-Type": "application/x-www-form-urlencoded"
                   }
        url = "https://pi.pardot.com/api/prospect/version/4/do/query"
        response = requests.post(url,
                                 params=params,
                                 headers=headers).json()
        if '@attributes' not in response or 'stat' not in response['@attributes']:
            raise ValueError(f"Pardot Request Failure: Corrupted Response")
        if response['@attributes']['stat'] != "ok":
            raise ValueError(f"Pardot Request Failure: {response['@attributes']['stat']}")

        prospects = response["result"]["prospect"]
        self.logger and self.logger.info(f"\t\tFound {len(prospects)} Prospects in Production created after {prospect_date_filter}:")
        for p in prospects:
            self.logger and self.logger.debug(
                f"\t\t\t{p['created_at']}: {p['first_name']} {p['last_name']} <{p['email']}>")
        return prospects

    def get_auth_handler(self, section_name: str) -> AuthHndlr:
        if section_name.startswith("pardot"):
            return TraditionalAuthHandler(self.parser.get(section_name, "username"),
                                          self.parser.get(section_name, "password"),
                                          self.parser.get(section_name, "userkey"),
                                          logger=self.logger)
        elif section_name.startswith("salesforce"):
            return OAuthHandler(self.parser.get(section_name, "user"),
                                self.parser.get(section_name, "password"),
                                self.parser.get(section_name, "consumer_key"),
                                self.parser.get(section_name, "consumer_secret"),
                                self.parser.get(section_name, "business_unit_id"),
                                token=self.parser.get(section_name, "token"),
                                logger=self.logger)

    def has_sections(self, sections: List[str]) -> bool:
        missing = [s for s in sections if s not in self.parser.sections()]
        valid = len(missing) == 0
        if not valid:
            self.logger and self.logger.info(f"\t\t...Skip, missing sections {missing} "
                                             f"from config file {self.config_file}")
        return valid

if __name__ == '__main__':
    logger = logging.getLogger("OAUTH_DEMO")
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('[{levelname:>8s}] {asctime} {name:s}: {message:s}', style='{')
    ch.setFormatter(formatter)
    ch.setLevel(logging.NOTSET)
    logger.addHandler(ch)
    config_file = Path("~/oauth_demo.ini").expanduser()
    demo = PardotAuthenticationDemo(config_file, logger=logger)
    demo.run()
