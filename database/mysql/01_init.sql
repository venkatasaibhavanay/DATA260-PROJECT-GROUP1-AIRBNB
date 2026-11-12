-- Runs once, on the first start of an empty MySQL volume.
-- The database and app user are created by the container from .env
-- (MYSQL_DATABASE / MYSQL_USER / MYSQL_PASSWORD).
--
-- Each service owner adds their own tables in a new numbered file, e.g.
--   02_users.sql (Nathan), 03_properties.sql (Sanjana), 04_bookings.sql (Bhavana)
-- The entrypoint runs these files against MYSQL_DATABASE. Keep one owner per table.


CREATE TABLE IF NOT EXISTS schema_info (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    component   VARCHAR(64)  NOT NULL,
    version     VARCHAR(32)  NOT NULL,
    applied_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_info (component, version) VALUES ('bootstrap', '0.1.0');
