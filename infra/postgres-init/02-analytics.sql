CREATE USER analytics_owner WITH PASSWORD 'analytics_reference_local';
CREATE SCHEMA IF NOT EXISTS business_analytics AUTHORIZATION analytics_owner;
GRANT CONNECT ON DATABASE bankpulse_domains TO analytics_owner;
