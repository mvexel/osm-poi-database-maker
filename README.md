# OpenStreetMap Smart-ish POI Database Generator

### *Populate a points-of-interest PostGIS database from an OSM data file*

OSM contains a lot of data, not all of it useful or correct, depending on what you want to use it for. A common use case for OSM data is Points Of Interest or POI: businesses, attractions, sports facilities, museums, et cetera. In OSM, there is no straightforward taxonomy of POI classes. You need to plow through the various values of `amenity`, `shop`, `tourism` and other tag keys to find what you want.

This script is not here to solve all your problems, but to get you 80% on your way. It queries TagInfo to generate a list of tags that are **commonly used and documented**<sup>1</sup>. You set which OSM keys to consider, and which specific key/value pairs to ignore. After you set these parameters, you run the script on an OSM data file (PBF is quickest) and enjoy your POI database.

The most important caveats are:

1. OSM Relations are not supported. Very few POI are represented as relations, so that should not matter to the vast majority of users.
2. POI that are represented as ways (polygons) in OSM are stored with their original geometry: you get a database with both points and polygons. The script could be more opinionated about this and store, for example, a centroid of an OSM way as the POI in the database, but I decided to leave that up to you. With the default settings, you can end up with some pretty large POI polygons, for example parks and universities. You can apply your own PostGIS magic to post-process those however you want. For example, you could simply delete the larger areas with something like `DELETE FROM WAYS WHERE ST_Area(ST_Transform(linestring, 2163)) > 10000;` (use your favorite local CRS for best results.)

<sup>1</sup> The [TagInfo key / value API](https://taginfo.openstreetmap.org/taginfo/apidoc#api_4_key_values) returns the fields `count` and `in_wiki` for each key/value pair. We use `in_wiki` to filter out those tags that are not documented in the wiki at all. You can set a lower threshold value for `count` in `settings.py`.

## Setup

1. Make sure you have PostgreSQL and PostGIS installed. The script is tested with PostgreSQL 14 and PostGIS 3.

2. Create your database
```
createdb -E UTF8 osm
psql -d osm -f schema.sql
```
(You may need to add credentials to access your PostgreSQL instance)

3. Create a virtual environment and install the Python dependencies.
```
python3 -m  venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
```

3. Retrieve an OSM data file for your area of interest. You can get bite-size ones from [GeoFabrik](http://download.geofabrik.de/).

4. Open `settings.py` and tweak the parameters to your liking. Each parameter is documented. 

## Usage

```
filter.py OSM_FILE
```

## Extras
If you want a database with only point features without discarding OSM polygons that have POI attributes, you can use the `ways_to_cantroids.sql` SQL script after populating the database. This script converts all polygons that are smaller than a reasonable threshold (the script uses 20000 m<sup>2</sup>) to nodes by taking the centroid of the polygon and incrementing the id value by 36000000000 to avoid conflicts in the overlapping id spaces. Any polygons larger than the threshold value are considered to be meaningless as point features.

## Thanks

Thanks to @joto and @lonvia for creating and maintaining `osmium` and `pyosmium`!

## Support

If you find this and / or my other work for the OSM community useful, please consider [supporting me on Patreon](https://patreon.com/mvexel). Thanks!