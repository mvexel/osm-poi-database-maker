# The root OSM tag keys you want to include.
# By default, all values that are used more than MIN_OCCURRENCES times
# (at the time of retrieval from TagInfo) in combination with each key in this list
# will be included.
KEYS = [
    "leisure",
    "shop",
    "amenity",
    "tourism",
    "craft",
    "healthcare",
    "office",
    "sport",
]

# Tags that occur fewer that the below amount of times in the entire OSM database will not be considered.
MIN_OCCURENCES = 1000

# You can set SKIP_WAYS to True if you would like to ignore ways altogether. Please bear in mind that
# you are likely to miss a significant amount of useful data, because OSM mapping conventions don't
# strictly dictate that a point of interest should be a separate point feature. Many POIs are instead
# defined as attributes on a building footprint.
SKIP_WAYS = False

# We will consider objects even if they do not have a name in OSM. You can override that default by setting
# SKIP_NO_NAME to True instead
SKIP_NO_NAME = False

# Some tags are internal to OSM and may not be useful to you, like "note" and "fixme". You can define a list
# of tag keys to strip from the objects here.
# TRIM_TAGS = ["note", "fixme"]
TRIM_TAGS = []

# You can add specific key=value pair combinations that you would like to exclude to the list below,
# as tuples of "key=value" strings. This is useful if, for example, you would like to have all amenity objects,
# but you're not interested in parking. In that case, you would add ("amenity=parking") to this list.
# You would still get all other "amenity" features. The entries can consist of a single tag, or a combination.
EXCLUDE_LIST = ()

# The PostgreSQL connection string to connect to your PostgreSQL database.
# See https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING for information
# on how to compose connection strings
PG_CONNECT_STRING = "dbname=osm"

# ================================================================
# Advanced Settings - you can probably leave these at the defaults
# ================================================================

# The number of objects to collect before flushing to the PostgreSQL database
WRITE_AFTER = 10000

import logging

LOG_LEVEL = logging.INFO
