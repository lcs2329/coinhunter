#!/usr/bin/env python3

import requests
import logging
import coloredlogs
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)
coloredlogs.install(level="INFO", fmt="%(message)s", logger=log)

urls_to_parse = []
known_urls = []

def get_sublinks(base_url, depth):
    log.debug(f"DEPTH: {depth}: Querying {base_url} for sublinks...")

    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, features="lxml")

    for link in soup.find_all("a", href=True):

        absolute_url = urljoin(base_url, link["href"]) 
        if absolute_url not in known_urls:
            known_urls.append(absolute_url)





parser = argparse.ArgumentParser()
parser.add_argument("-u", "--url", type=str, metavar="BASE URL", help="Base URL to begin spidering.")
parser.add_argument("-d", "--depth", type=int, default=3, help="Maximum recursive depth.")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
parser.add_argument("-t", "--threads", type=int, default=5, help="Maximum number of concurrent threads.")
args = parser.parse_args()

# if we threw the verbose flag, then enable debug logging
if args.verbose:
    coloredlogs.install(
        level="DEBUG", fmt="[%(asctime)s] [%(levelname)-8s] %(message)s", logger=log
    )

pool = ThreadPoolExecutor(args.threads)


base_url = args.url
if not base_url.startswith("http://") or not base_url.startswith("https://"):
    base_url = "http://" + base_url

get_sublinks(base_url, args.depth)