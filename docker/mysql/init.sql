-- =============================================================================
-- docker/mysql/init.sql
-- Runs ONCE on first container start (when the data volume is empty).
-- Creates the application database and grants the app user privileges.
-- =============================================================================

-- The database itself is created by MYSQL_DATABASE env var,
-- but we set charset explicitly to guarantee utf8mb4.
ALTER DATABASE `employee_management_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Grant the app user full access to the app database only (least privilege).
-- Root should never be used by the application.
GRANT ALL PRIVILEGES ON `employee_management_db`.* TO 'hris_user'@'%';
FLUSH PRIVILEGES;
