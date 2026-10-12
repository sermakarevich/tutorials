-- The read-only user OpenMetadata connects with (never the admin user).
CREATE USER om_reader WITH PASSWORD 'reader123';
GRANT CONNECT ON DATABASE brightcup TO om_reader;
GRANT USAGE ON SCHEMA raw, analytics TO om_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, analytics TO om_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE shop_admin IN SCHEMA raw, analytics GRANT SELECT ON TABLES TO om_reader;
GRANT pg_read_all_stats TO om_reader;  -- lets ingestion read pg_stat_statements (query log)
