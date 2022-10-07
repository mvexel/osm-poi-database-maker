#!/usr/bin/env python3

from copy import deepcopy
from datetime import datetime
from io import StringIO
import os
import sys
import json
import requests
import osmium
import psycopg2
import settings


class PostgresWriter:
    """
    Class to handle interaction with the Postgres database
    """

    def __init__(self, connect_string, rows, osm_type) -> None:
        super().__init__()
        self._connect_string = connect_string
        self._rows = rows
        self._osm_type = osm_type

    def write_osm_objects(self):
        """
        Write OSM objects to the PostgreSQL database
        """
        try:
            with psycopg2.connect(self._connect_string) as conn:
                with conn.cursor() as cursor:
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
            print(
                """ERROR: A duplicate OSM id was encountered while attempting to copy OSM objects to PostgreSQL.
Most likely, you are trying to populate an OSM database that already has OSM data in it, 
for example if you ran this script previously with the same OSM input file."""
            )
            sys.exit(1)
        except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
            print(
                """ERROR: Table does not exist. 
Please make sure you have initialized your OSM database with the Osmosis schema"""
            )
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Something unexpected happened.\n\n{e.message}")


class FilterHandler(osmium.SimpleHandler):
    def __init__(self, tags_of_interest, min_occurrences) -> None:
        super().__init__()
        self.toi = tags_of_interest
        self.min_occurrences = min_occurrences
        self.node_rows = []
        self.area_rows = []

    def _sanitize(self, raw_str):
        return (
            raw_str.replace('"', '\\"').replace("\\", "\\\\").replace("\n", "||e'\\n'")
        )

    def _tags_as_hstore(self, osm_tags):
        return ",".join(
            [
                '"{key}"=>"{value}"'.format(
                    key=self._sanitize(tag.k), value=self._sanitize(tag.v)
                )
                for tag in osm_tags
            ]
        )

    def _obj_geom_as_wkb(self, osm_obj):
        """
        Produces a WKB representation of the input osmium OSM object (node or area)
        """
        factory = osmium.geom.WKBFactory()
        if isinstance(osm_obj, osmium.osm.Node):
            return factory.create_point(osm_obj)
        elif isinstance(osm_obj, osmium.osm.Area):
            # print(osm_obj)
            return factory.create_multipolygon(osm_obj)

    def _osm_as_pg_row(self, osm_obj):
        # COPY public.nodes (id, version, user_id, tstamp, changeset_id, tags, geom) FROM stdin;
        # 83516871	14	0	2020-02-02 08:51:47	0	"highway"=>"traffic_signals", "traffic_signals"=>"signal"	0101000020E6100000278A90BA1DF55BC06A4826F103614440
        return (
            "{id}\t{version}\t{uid}\t{tstamp}\t{changeset_id}\t{tags}\t{geom}".format(
                id=osm_obj.id,
                version=osm_obj.version,
                uid=osm_obj.uid,
                tstamp=osm_obj.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                changeset_id=osm_obj.changeset,
                tags=self._tags_as_hstore(osm_obj.tags),
                geom=self._obj_geom_as_wkb(osm_obj),
            )
        )

    def flush_to_pg(self, rows, osm_type):
        pg_writer = PostgresWriter(settings.PG_CONNECT_STRING, rows, osm_type)
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
                if isinstance(obj, osmium.osm.Node):
                    self.node_rows.append(self._osm_as_pg_row(obj))
                    if len(self.node_rows) == settings.WRITE_AFTER:
                        print(f"writing {settings.WRITE_AFTER} nodes to Postgres...")
                        # print("\n".join(self.node_rows))
                        self.flush_to_pg(self.node_rows, "nodes")
                        self.node_rows.clear()
                    return
                if isinstance(obj, osmium.osm.Area):
                    self.area_rows.append(self._osm_as_pg_row(obj))
                    if len(self.area_rows) == settings.WRITE_AFTER:
                        print(f"writing {settings.WRITE_AFTER} areas to Postgres...")
                        # print("\n".join(self.area_rows))
                        self.flush_to_pg(self.area_rows, "ways")
                        self.area_rows.clear()
                    return

    def node(self, n):
        self._filter(n)

    def area(self, a):
        if not settings.SKIP_WAYS:
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


if __name__ == "__main__":
    print(f"welcome to {sys.argv[0]}")
    if len(sys.argv) != 2:
        print("usage: filter.py OSMFILE")
    # Read existing tags.json if we retrieved it recently
    # TODO add a parameter to define what "recently" is and check the existing tags.json file to see if it needs updating.
    if os.path.exists("tags.json"):
        print("tags file exists")
        with open("tags.json") as fh:
            tags = json.loads(fh.read())
    # If we don't have a tags.json yet, call the TagInfo API to retrieve
    # values and usage data for each key of interest.
    else:
        print("we don't have a tags file, retrieving from TagInfo...")
        tags = {
            "retrieval_date": datetime.now().isoformat(timespec="minutes"),
            "data": {},
        }
        for osm_key in settings.KEYS:
            print(f"retrieving TagInfo data for {osm_key}...")
            tags["data"][osm_key] = retrieve_taginfo(osm_key)
        with open("tags.json", "w") as fh:
            fh.write(json.dumps(tags))

    # Create the osmium handler instance
    fh = FilterHandler(tags["data"], settings.MIN_OCCURENCES)
    # We need locations=True so that osmium keeps the node locations cached in order to recreate the area geometries
    fh.apply_file(sys.argv[1], locations=True)
    # for larger files we should use a different index
    # support for this is not compiled into the pyosmium binary by default.
    # fh.apply_file(sys.argv[1], locations=True, idx="dense_mmap_array")
    if len(fh.node_rows) > 0:
        print(f"flushing final {len(fh.node_rows)} nodes to Postgres...")
        fh.flush_to_pg(fh.node_rows, "nodes")
    if len(fh.area_rows) > 0:
        print(f"flushing final {len(fh.area_rows)} areas to Postgres...")
        fh.flush_to_pg(fh.area_rows, "ways")
