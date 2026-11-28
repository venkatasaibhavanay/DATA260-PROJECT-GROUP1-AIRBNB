-- User service schema (owner: Nathan Pak). API design document sections 4, 6 and 13.
-- Runs automatically on the first start of an empty MySQL volume. For an existing volume:
--   docker exec -i data260-g1-mysql sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < database/mysql/02_users.sql
-- Only user-service writes these tables.

CREATE TABLE IF NOT EXISTS guests (
    guest_id                 INT           NOT NULL AUTO_INCREMENT,
    first_name               VARCHAR(60)   NOT NULL,
    last_name                VARCHAR(60)   NOT NULL,
    email                    VARCHAR(254)  NOT NULL,
    password_hash            VARCHAR(100)  NOT NULL,
    phone                    VARCHAR(16)   NULL,
    location                 VARCHAR(120)  NOT NULL,
    profile_photo_url        VARCHAR(255)  NULL,
    preferences              JSON          NULL,
    saved_properties_count   INT           NOT NULL DEFAULT 0,
    booking_count            INT           NOT NULL DEFAULT 0,
    status                   ENUM('active','deleted') NOT NULL DEFAULT 'active',
    profile_created_datetime DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_datetime         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_datetime         DATETIME      NULL,
    PRIMARY KEY (guest_id),
    UNIQUE KEY uq_guests_email (email),
    KEY ix_guests_name (last_name, first_name),
    KEY ix_guests_location (location),
    CONSTRAINT ck_guests_counts CHECK (saved_properties_count >= 0 AND booking_count >= 0)
) ENGINE=InnoDB AUTO_INCREMENT=1001 DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hosts (
    host_id                  INT           NOT NULL AUTO_INCREMENT,
    name                     VARCHAR(120)  NOT NULL,
    email                    VARCHAR(254)  NOT NULL,
    password_hash            VARCHAR(100)  NOT NULL,
    phone                    VARCHAR(16)   NULL,
    profile_photo_url        VARCHAR(255)  NULL,
    verification_status      ENUM('unverified','pending','verified') NOT NULL DEFAULT 'unverified',
    access_level             ENUM('standard','superhost','suspended') NOT NULL DEFAULT 'standard',
    response_rate            DECIMAL(3,2)  NULL,
    response_time_minutes    INT           NULL,
    host_since               DATE          NOT NULL,
    status                   ENUM('active','deleted') NOT NULL DEFAULT 'active',
    created_datetime         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_datetime         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (host_id),
    UNIQUE KEY uq_hosts_email (email),
    CONSTRAINT ck_hosts_response_rate CHECK (response_rate IS NULL OR (response_rate >= 0 AND response_rate <= 1))
) ENGINE=InnoDB AUTO_INCREMENT=501 DEFAULT CHARSET=utf8mb4;

-- Seeded only (python -m app.seed_admin). Admins never sign up through the API.
CREATE TABLE IF NOT EXISTS admins (
    admin_id                 INT           NOT NULL AUTO_INCREMENT,
    name                     VARCHAR(120)  NOT NULL,
    email                    VARCHAR(254)  NOT NULL,
    password_hash            VARCHAR(100)  NOT NULL,
    created_datetime         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (admin_id),
    UNIQUE KEY uq_admins_email (email)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4;

-- user-host-metrics: one row per guest-initiated thread, used for response_rate / response_time.
CREATE TABLE IF NOT EXISTS host_thread_responses (
    thread_id                VARCHAR(64)   NOT NULL,
    host_id                  INT           NOT NULL,
    guest_first_message_at   DATETIME      NOT NULL,
    host_first_reply_at      DATETIME      NULL,
    PRIMARY KEY (thread_id),
    KEY ix_htr_host_started (host_id, guest_first_message_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Consumer idempotency (shared.kafka.idempotency).
CREATE TABLE IF NOT EXISTS user_processed_events (
    consumer_group           VARCHAR(64)   NOT NULL,
    idempotency_key          VARCHAR(256)  NOT NULL,
    processed_at             TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (consumer_group, idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO schema_info (component, version) VALUES ('user-service', '1.0.0');
