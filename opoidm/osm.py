import logging
from os import stat

import requests

import settings
from opoidm.handlers import FilterHandler

logger = logging.getLogger(__name__)


class TagInfo:
    def __init__(self) -> None:
        super.__init__(self)

    @staticmethod
    def get_values(key: str) -> dict:
        """
        Retrieves all values for this tag key from the TagInfo wiki, and returns those values and their counts that have a corresponding OSM wiki entry.
        """
        TAGINFO_VALUES_API_URL = f"https://taginfo.openstreetmap.org/api/4/key/values?key={key}&page=1&rp=100&sortname=count_ways&sortorder=desc"
        tag_values = requests.get(TAGINFO_VALUES_API_URL).json()
        return dict(
            [
                (item["value"], item["count"])
                for item in tag_values["data"]
                if ";" not in item["value"] and item["in_wiki"]
            ]
        )


class OsmFileProcessor:
    def __init__(self, path, tags) -> None:
        self._path = path
        self._tags = tags

    def process(self):
        # Create the osmium handler instance
        fh = FilterHandler(self._tags["data"], settings.MIN_OCCURENCES)

        # We need locations=True so that osmium keeps the node locations cached in order to recreate the area geometries
        fh.apply_file(self._path, locations=True)
        # for larger files we should use a different index
        # support for this is not compiled into the pyosmium binary by default.
        # fh.apply_file(sys.argv[1], locations=True, idx="dense_mmap_array")
        if len(fh.node_rows) > 0:
            fh.flush_to_pg(fh.node_rows, "nodes")
        if len(fh.area_rows) > 0:
            fh.flush_to_pg(fh.area_rows, "ways")
