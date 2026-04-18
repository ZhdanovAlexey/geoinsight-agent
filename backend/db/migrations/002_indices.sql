CREATE INDEX zones_city_idx ON zones (city);
CREATE INDEX zones_geom_gist ON zones USING GIST (geom);
CREATE INDEX zones_centroid_gist ON zones USING GIST (centroid);

CREATE INDEX zd_zid_idx ON zone_demographics (zid);
CREATE INDEX zd_filter_idx ON zone_demographics (income, age, gender);

CREATE INDEX zdyn_zid_ts_idx ON zone_dynamics (zid, ts);

CREATE INDEX traj_home_idx ON trajectories (home_zid);
CREATE INDEX traj_job_idx ON trajectories (job_zid);
CREATE INDEX traj_country_idx ON trajectories (country_name) WHERE country_name IS NOT NULL;
