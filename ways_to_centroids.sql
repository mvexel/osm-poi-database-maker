WITH la AS (
    SELECT id + 36000000000, version, user_id, tstamp, changeset_id, tags, ST_Centroid(linestring) geom
    FROM ways 
    WHERE ST_Area(linestring :: geography) <= 20000
) 
INSERT INTO nodes SELECT * FROM la;
