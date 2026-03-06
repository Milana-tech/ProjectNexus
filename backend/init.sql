CREATE TABLE IF NOT EXISTS zones
(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO zones (name) VALUES
('zone_a'),
('zone_b'),
('zone_c');