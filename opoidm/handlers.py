import logging

import osmium

import settings
from opoidm.db import PostgresWriter

logger = logging.getLogger(__name__)


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
        logger.info("Initialized data handler")

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
        # dismiss any object with tag combinations in the EXCLUDE_LIST.
        for exclude_tuple in settings.EXCLUDE_LIST:
            if set([t.__str__() for t in obj.tags]) >= set(exclude_tuple):
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
                            self.flush_to_pg(self.node_rows, "nodes")
                            self.node_rows.clear()
                        return
                if isinstance(obj, osmium.osm.Area):
                    row = self._osm_as_pg_row(obj)
                    if obj.id not in self.invalid_ways:
                        self.area_rows.append(row)
                        if len(self.area_rows) == settings.WRITE_AFTER:
                            self.flush_to_pg(self.area_rows, "ways")
                            self.area_rows.clear()
                        return

    def node(self, n):
        self._node_counter += 1
        if not self._node_counter % 1000000:
            logger.info(f"{int(self._node_counter / 1000000)}M nodes evaluated...")
        self._filter(n)

    def area(self, a):
        self._way_counter += 1
        if not self._way_counter % 1000000:
            logger.info(f"{int(self._way_counter / 1000000)}M ways evaluated...")
        if not settings.SKIP_WAYS and not isinstance(a, osmium.osm.Relation):
            self._filter(a)

    def relation(self, r):
        # We do not support relations
        pass
