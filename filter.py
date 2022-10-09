#!/usr/bin/env python3

import json
import logging
import os
import sys
from datetime import datetime

import requests

import settings
from opoidm.osm import OsmFileProcessor, TagInfo

# # Initialize global logger
# logger = logging.getLogger("osm-poi-database-maker")
# logger.setLevel(settings.LOG_LEVEL)
# handler = logging.StreamHandler(sys.stdout)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# handler.setFormatter(formatter)
# logger.addHandler(handler)


def main():
    logger = logging.getLogger(__name__)
    logger.info(f"welcome to osm-poi-database-maker")

    # Read existing tags.json if we retrieved it recently
    # TODO add a parameter to define what "recently" is and check the existing tags.json file to see if it needs updating.
    if os.path.exists("tags.json"):
        logger.info("tags file exists")
        with open("tags.json") as fh:
            tags = json.loads(fh.read())

    # If we don't have a tags.json yet, call the TagInfo API to retrieve
    # values and usage data for each key of interest.
    else:
        logger.info("we don't have a tags file, retrieving from TagInfo...")
        tags = {
            "retrieval_date": datetime.now().isoformat(timespec="minutes"),
            "data": {},
        }
        for osm_key in settings.KEYS:
            logger.info(f"retrieving TagInfo data for {osm_key}...")
            tags["data"][osm_key] = TagInfo.get_values(osm_key)
        with open("tags.json", "w") as fh:
            fh.write(json.dumps(tags))

    processor = OsmFileProcessor(sys.argv[1], tags)
    processor.process()


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("usage: filter.py OSMFILE")
        sys.exit(1)

    logging.basicConfig(
        stream=sys.stdout,
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    main()
