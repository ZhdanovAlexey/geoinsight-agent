CREATE EXTENSION IF NOT EXISTS postgis;

-- Zones (250x250m polygons)
CREATE TABLE zones (
    zid           BIGINT PRIMARY KEY,
    city          TEXT NOT NULL,
    geom          GEOMETRY(Polygon, 4326) NOT NULL,
    centroid      GEOMETRY(Point, 4326) GENERATED ALWAYS AS (ST_Centroid(geom)) STORED
);

-- Zone demographics (aggregates)
CREATE TABLE zone_demographics (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zid       BIGINT NOT NULL REFERENCES zones(zid),
    income    SMALLINT NOT NULL,
    age       SMALLINT NOT NULL,
    gender    SMALLINT NOT NULL,
    cnt       INTEGER NOT NULL,
    home_zid  BIGINT,
    job_zid   BIGINT
);

-- Zone dynamics (time series)
CREATE TABLE zone_dynamics (
    zid       BIGINT NOT NULL REFERENCES zones(zid),
    ts        TIMESTAMPTZ NOT NULL,
    income    SMALLINT NOT NULL,
    age       SMALLINT NOT NULL,
    gender    SMALLINT NOT NULL,
    cnt       INTEGER NOT NULL
);

-- Trajectories (optional for MVP)
CREATE TABLE trajectories (
    code         TEXT NOT NULL,
    age_group    TEXT,
    home_zid     BIGINT,
    job_zid      BIGINT,
    hourly_zids  JSONB,
    roaming_type TEXT,
    country_name TEXT
);
