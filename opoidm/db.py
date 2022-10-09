import logging
import sys
from io import StringIO

import psycopg2

import settings

logger = logging.getLogger(__name__)


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
        logger.info(f"Writing {len(self._rows)} POI to database")
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
