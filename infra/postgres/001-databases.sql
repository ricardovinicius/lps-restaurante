\set ON_ERROR_STOP on
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
\getenv service_password CONFIGURATION_DB_PASSWORD
CREATE ROLE mesa_configuration LOGIN PASSWORD :'service_password';
CREATE DATABASE mesa_configuration OWNER mesa_configuration;
REVOKE ALL ON DATABASE mesa_configuration FROM PUBLIC;
GRANT CONNECT ON DATABASE mesa_configuration TO mesa_configuration;
\getenv service_password CATALOG_DB_PASSWORD
CREATE ROLE mesa_catalog LOGIN PASSWORD :'service_password';
CREATE DATABASE mesa_catalog OWNER mesa_catalog;
REVOKE ALL ON DATABASE mesa_catalog FROM PUBLIC;
GRANT CONNECT ON DATABASE mesa_catalog TO mesa_catalog;
\getenv service_password ORDERS_DB_PASSWORD
CREATE ROLE mesa_orders LOGIN PASSWORD :'service_password';
CREATE DATABASE mesa_orders OWNER mesa_orders;
REVOKE ALL ON DATABASE mesa_orders FROM PUBLIC;
GRANT CONNECT ON DATABASE mesa_orders TO mesa_orders;
\getenv service_password DELIVERIES_DB_PASSWORD
CREATE ROLE mesa_deliveries LOGIN PASSWORD :'service_password';
CREATE DATABASE mesa_deliveries OWNER mesa_deliveries;
REVOKE ALL ON DATABASE mesa_deliveries FROM PUBLIC;
GRANT CONNECT ON DATABASE mesa_deliveries TO mesa_deliveries;
\getenv service_password TABLES_DB_PASSWORD
CREATE ROLE mesa_tables LOGIN PASSWORD :'service_password';
CREATE DATABASE mesa_tables OWNER mesa_tables;
REVOKE ALL ON DATABASE mesa_tables FROM PUBLIC;
GRANT CONNECT ON DATABASE mesa_tables TO mesa_tables;
