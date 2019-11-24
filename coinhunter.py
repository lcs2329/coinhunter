#!/usr/bin/env python3

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from urllib.parse import urljoin, urlparse

import coloredlogs
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
coloredlogs.install(level="INFO", fmt="%(message)s", logger=log)


def get_mining_domains():
    miners = []
    response = requests.get(
        "https://raw.githubusercontent.com/mozilla-services/shavar-prod-lists/master/disconnect-blacklist.json"
    )
    if response.status_code != 200:
        log.error("Unable to receive updated list of miners. Exiting...")
        return

    data = json.loads(response.text)
    cryptominers = data["categories"]["Cryptomining"]
    for domain in cryptominers:
        for subdomain in domain:
            for url in domain[subdomain]:
                mining_domains = domain[subdomain][url]
                for mining_domain in mining_domains:
                    if len(mining_domain) > 1:
                        miners.append(mining_domain)

    log.info(f"Found {len(miners)} mining domains.")
    return miners


class coin_scraper:
    def __init__(self, base_url, max_depth, threads, mining_domains):

        self.base_url = base_url
        self.root_url = "{}://{}".format(
            urlparse(self.base_url).scheme, urlparse(self.base_url).netloc
        )
        self.max_depth = max_depth
        self.pool = ThreadPoolExecutor(max_workers=threads)
        self.mining_domains = mining_domains
        self.scraped_pages = set([])
        self.miner_count = 0
        self.to_crawl = Queue()
        self.to_crawl.put({"url": self.base_url, "depth": 1})

    def post_scrape_callback(self, response):
        result = response.result()
        if not result:
            return

        response = result["response"]
        depth = result["depth"]

        if response and response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        else:
            return

        scripts = soup.find_all("script")

        # see if we have scripts on the page, otherwise we
        # are scanning a remote script
        if len(scripts) > 0:

            log.debug(f"Scanning for scripts on {response.url}...")
            for script in scripts:

                # if it has a source, its a remote
                if "src" in script.attrs.keys():

                    # see if the source location lines up to one of our
                    # known cryptojacking domains
                    netloc = urlparse(script.attrs["src"]).netloc
                    if netloc in self.mining_domains:

                        log.warning(
                            f"Found link to remote cryptojacking provider:\n"
                            f"Source: {response.url}\n"
                            f"Destination:\n{script.attrs['src']}"
                        )

                    # add the script to the queue to be scanned
                    url = urljoin(self.root_url, script.attrs["src"])
                    self.to_crawl.put({"url": url, "depth": depth})

                else:
                    # otherwise, this is a local script. see if any of the
                    # known domains shows up in the text
                    script_text = script.text.lower()
                    for miner in self.mining_domains:
                        if miner in script_text:
                            log.warning(
                                f"Found cryptomining script:\n"
                                f"Source: {response.url}\n"
                                f"Contents:\n{script}"
                            )
                            self.miner_count += 1

        else:
            # if the page has no scripts, its likely a raw script, so we will
            # scan the code of the script for any reference to our known
            # cryptojacking providers
            script_text = response.text.lower()
            for miner in self.mining_domains:
                if miner in script_text:
                    log.warning(
                        f"Found cryptomining script:\n"
                        f"Source: {response.url}\n"
                        f"Contents:\n{script}"
                    )
                    self.miner_count += 1

        # add all sublinks to the queue to be scanned
        for link in soup.find_all("a", href=True):
            url = urljoin(self.root_url, link["href"])
            if url not in self.scraped_pages:
                self.to_crawl.put({"url": url, "depth": depth + 1})

    def scrape_page(self, target):
        url = target["url"]
        depth = target["depth"]
        if depth > self.max_depth:
            return

        log.debug(f"Scraping URL: {url}, depth: {depth}")

        try:
            response = requests.get(url, timeout=(3, 30))
            if response:
                return {"response": response, "depth": depth}

        except requests.RequestException:
            return

    def run_scraper(self):
        while True:
            try:
                target = self.to_crawl.get(timeout=60)
                target_url = target["url"]

                if target_url not in self.scraped_pages:
                    self.scraped_pages.add(target_url)
                    job = self.pool.submit(self.scrape_page, target)
                    job.add_done_callback(self.post_scrape_callback)

            except Empty:
                return len(self.scraped_pages), self.miner_count

            except Exception as e:
                log.exception(e)
                continue

            except KeyboardInterrupt:
                log.info("Received keyboard interrupt, exiting...")
                log.info(
                    f"At time of interrupt, {len(self.scraped_pages)} pages were scanned."
                )
                exit()

            if len(self.scraped_pages) % 100 == 0:
                log.info(f"{len(self.scraped_pages)} pages scanned.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        metavar="BASE URL",
        required=True,
        help="Base URL to begin spidering.",
    )
    parser.add_argument(
        "-d", "--depth", type=int, default=3, help="Maximum recursive depth."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging."
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=5,
        help="Maximum number of concurrent threads.",
    )
    args = parser.parse_args()

    # if we threw the verbose flag, then enable debug logging
    if args.verbose:
        coloredlogs.install(
            level="DEBUG", fmt="[%(asctime)s] [%(levelname)-8s] %(message)s", logger=log
        )

    base_url = args.url
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "http://" + base_url

    miners = get_mining_domains()
    if not miners:
        exit(1)

    log.info(f"Initiating cryptocurrency mining scans at {args.url}...")

    s = coin_scraper(base_url, args.depth, args.threads, miners)
    total_pages, miners = s.run_scraper()

    log.info(
        f"Scans complete. Analyzed {total_pages} webpages, found {miners} cryptocurrency miners."
    )
