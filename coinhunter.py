#!/usr/bin/env python3

import requests
import logging
import coloredlogs
import argparse
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import re
import threading
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)
coloredlogs.install(level="INFO", fmt="%(message)s", logger=log)

urls_to_parse = {}
known_urls = []


def get_sublinks(base_url, depth):
    if depth >= args.depth:
        return

    log.debug(f"DEPTH: {depth}: Querying {base_url} for sublinks...")

    response = requests.get(base_url, timeout=10)
    if response.status_code != 200:
        log.error(f"Url {base_url} returned {response.status_code}")
        return

    soup = BeautifulSoup(response.text, features="lxml")

    remote_scripts = []
    for script in soup.find_all("script"):
        if "src" in script.attrs.keys():
            absolute_url = urljoin(base_url, script.attrs["src"])
            log.debug(f"Remote script found, src = {absolute_url}")
        else:
            if "coinhive" in script.text.lower():
                log.warning(f"Found coinhive script: \nSource: {base_url} \nContents:\n{script}")

    for link in soup.find_all("a", href=True):

        absolute_url = urljoin(base_url, link["href"]) 
        if absolute_url not in known_urls and absolute_url not in urls_to_parse.keys():
            log.debug(f"Adding {absolute_url} to links to process...")
            urls_to_parse[absolute_url] = depth + 1


def watch_for_links():
    log.debug("Spawning base thread to watch for URLs...")
    while True:
        if len(urls_to_parse) > 0:
            for link in list(urls_to_parse):
                pool.submit(get_sublinks, link, urls_to_parse[link])
                known_urls.append(link)
                del urls_to_parse[link]


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
t = threading.Thread(target=watch_for_links)
t.start()

base_url = args.url
if not base_url.startswith("http://") or not base_url.startswith("https://"):
    base_url = "http://" + base_url

#get_sublinks(base_url, 0)
urls_to_parse[base_url] = 0