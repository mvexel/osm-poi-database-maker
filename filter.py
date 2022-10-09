#!/usr/bin/env python3

from datetime import datetime
from io import StringIO
import os
import sys
import json
import requests
import osmium
import psycopg2
import settings
import logging

# Initialize global logger
logger = logging.getLogger("osm-poi-database-maker")
logger.setLevel(settings.LOG_LEVEL)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class PostgresWriter:
    """
    Class to handle interaction with the Postgres database
    """

    def __init__(self, rows, osm_type) -> None:
        super().__init__()
        self._rows = rows
        self._osm_type = osm_type

    def write_osm_objects(self):
        """
        Write OSM objects to the PostgreSQL database
        """
        try:
            with psycopg2.connect(settings.PG_CONNECT_STRING) as pg_conn:
                with pg_conn.cursor() as cursor:
                    psycopg2.extensions.register_type(
                        psycopg2.extensions.UNICODE, cursor
                    )
                    geom_column = "geom" if self._osm_type == "nodes" else "linestring"
                    with StringIO("\n".join([row for row in self._rows])) as fh:
                        cursor.copy_from(
                            fh,
                            self._osm_type,
                            columns=(
                                "id",
                                "version",
                                "user_id",
                                "tstamp",
                                "changeset_id",
                                "tags",
                                geom_column,
                            ),
                        )
        except psycopg2.errors.UniqueViolation:
            logger.error(
                """A duplicate OSM id was encountered while attempting to copy OSM objects to PostgreSQL.
Most likely, you are trying to populate an OSM database that already has OSM data in it, 
for example if you ran this script previously with the same OSM input file."""
            )
            sys.exit(1)
        except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
            logger.error(
                """Table does not exist. 
Please make sure you have initialized your OSM database with the Osmosis schema"""
            )
            sys.exit(1)
        except Exception as e:
            with open("logs/error_obj_list.csv", "w") as fh:
                fh.write("\n".join([row for row in self._rows]))
            logger.error(
                f"{type(e)} - Something unexpected happened. All we know is this: {e}"
            )
            sys.exit(1)


class FilterHandler(osmium.SimpleHandler):
    def __init__(self, tags_of_interest, min_occurrences) -> None:
        super().__init__()
        self.toi = tags_of_interest
        self.min_occurrences = min_occurrences
        self.node_rows = []
        self.area_rows = []
        self.invalid_nodes = []
        self.invalid_ways = []
        self._node_counter = 0
        self._way_counter = 0

    def _sanitize(self, raw_str: str):
        return (
            raw_str.replace("\\\\", "\\\\\\\\")
            .replace('"', '\\\\"')
            .replace("\n\r", "\\\\r")
            .replace("\n", "\\\\r")
            .replace("\r", "\\\\r")
            .replace("\t", "\\\\t")
        )

    def _tags_as_hstore(self, osm_tags):
        return ",".join(
            [
                '"{key}"=>"{value}"'.format(
                    key=self._sanitize(tag.k), value=self._sanitize(tag.v)
                )
                for tag in osm_tags
                if not tag.k in settings.TRIM_TAGS
            ]
        )

    def _obj_geom_as_wkb(self, osm_obj):
        """
        Produces a WKB representation of the input osmium OSM object (node or area)
        """
        factory = osmium.geom.WKBFactory()
        if isinstance(osm_obj, osmium.osm.Node):
            try:
                return factory.create_point(osm_obj)
            except RuntimeError:
                (
                    ": encountered an invalid geometry n{}".format(
                        osm_obj.id,
                    )
                )
                self.invalid_nodes.append(osm_obj.id)
        if isinstance(osm_obj, osmium.osm.Area):
            try:
                return factory.create_multipolygon(osm_obj)
            except RuntimeError:
                logger.warning(
                    "Encountered an invalid geometry w{}".format(
                        osm_obj.orig_id(),
                    )
                )
                self.invalid_ways.append(osm_obj.id)

    def _osm_as_pg_row(self, osm_obj):
        return (
            "{id}\t{version}\t{uid}\t{tstamp}\t{changeset_id}\t{tags}\t{geom}".format(
                id=osm_obj.id
                if isinstance(osm_obj, osmium.osm.Node)
                else osm_obj.orig_id(),
                version=osm_obj.version,
                uid=osm_obj.uid,
                tstamp=osm_obj.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                changeset_id=osm_obj.changeset,
                tags=self._tags_as_hstore(osm_obj.tags),
                geom=self._obj_geom_as_wkb(osm_obj),
            )
        )

    def flush_to_pg(self, rows, osm_type):
        pg_writer = PostgresWriter(rows, osm_type)
        pg_writer.write_osm_objects()

    def _filter(self, obj) -> None:
        """
        Generic filter function that operates on the desired OSM types.
        To use, call self._filter(obj) on the node() or area()
        callback functions.
        """
        # dismiss any object with no tags
        if not obj.tags:
            return
        # dismiss objects that have no name, unless the user wants them
        if settings.SKIP_NO_NAME and "name" not in obj.tags:
            return
        # dismiss any object with tags in the EXCLUDE_LIST.
        for t in obj.tags:
            if t.__str__() in settings.EXCLUDE_LIST:
                return
        # iterate over those objects that have one of the keys we're interested in
        for key in set(self.toi.keys()).intersection([t.k for t in obj.tags]):
            if obj.tags[key] in [
                val
                for val in self.toi[key]
                if self.toi[key][val] > self.min_occurrences
            ]:
                # we have an object of interest. add it to the list of nodes or areas of interest
                # Check if we reached the amount of objects by which we want to flush to PG
                # If so, write to postgres....
                # ...and clear the list.
                if (
                    isinstance(obj, osmium.osm.Node)
                    and obj.id not in self.invalid_nodes
                ):
                    row = self._osm_as_pg_row(obj)
                    if obj.id not in self.invalid_nodes:
                        self.node_rows.append(row)
                        if len(self.node_rows) == settings.WRITE_AFTER:
                            logger.info(
                                f"writing {settings.WRITE_AFTER} nodes to Postgres..."
                            )
                            # print("\n".join(self.node_rows))
                            self.flush_to_pg(self.node_rows, "nodes")
                            self.node_rows.clear()
                        return
                if isinstance(obj, osmium.osm.Area):
                    row = self._osm_as_pg_row(obj)
                    if obj.id not in self.invalid_ways:
                        self.area_rows.append(row)
                        if len(self.area_rows) == settings.WRITE_AFTER:
                            logger.info(
                                f"writing {settings.WRITE_AFTER} areas to Postgres..."
                            )
                            # print("\n".join(self.area_rows))
                            self.flush_to_pg(self.area_rows, "ways")
                            self.area_rows.clear()
                        return

    def node(self, n):
        self._node_counter += 1
        if not self._node_counter % 1000000:
            logger.info(
                f"Another 1M nodes evaluated, {self._node_counter / 1000000}M total"
            )
        self._filter(n)

    def area(self, a):
        self._way_counter += 1
        if not self._way_counter % 1000000:
            logger.info(
                f"Another 1M ways evaluated, {self._way_counter / 1000000}M total"
            )
        if not settings.SKIP_WAYS and not isinstance(a, osmium.osm.Relation):
            self._filter(a)

    def relation(self, r):
        # We do not support relations
        pass


def retrieve_taginfo(tag: str) -> dict:
    """
    Retrieves all values for this tag key from the TagInfo wiki, and returns those values and their counts that have a corresponding OSM wiki entry.
    """
    TAGINFO_VALUES_API_URL = f"https://taginfo.openstreetmap.org/api/4/key/values?key={tag}&page=1&rp=100&sortname=count_ways&sortorder=desc"
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
        fh = FilterHandler(tags["data"], settings.MIN_OCCURENCES)

        # We need locations=True so that osmium keeps the node locations cached in order to recreate the area geometries
        fh.apply_file(self._path, locations=True)
        # for larger files we should use a different index
        # support for this is not compiled into the pyosmium binary by default.
        # fh.apply_file(sys.argv[1], locations=True, idx="dense_mmap_array")
        if len(fh.node_rows) > 0:
            logger.info(f"flushing final {len(fh.node_rows)} nodes to Postgres...")
            fh.flush_to_pg(fh.node_rows, "nodes")
        if len(fh.area_rows) > 0:
            logger.info(f"flushing final {len(fh.area_rows)} areas to Postgres...")
            fh.flush_to_pg(fh.area_rows, "ways")


if __name__ == "__main__":

    logger.info(f"welcome to osm-poi-database-maker")

    if len(sys.argv) != 2:
        print("usage: filter.py OSMFILE")
        sys.exit(1)

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
            tags["data"][osm_key] = retrieve_taginfo(osm_key)
        with open("tags.json", "w") as fh:
            fh.write(json.dumps(tags))

    processor = OsmFileProcessor(sys.argv[1], tags)
    processor.process()
