-- migration_v4.sql
-- Idempotent migration to add username and password_hash to students table
ALTER TABLE students 
ADD COLUMN IF NOT EXISTS username text UNIQUE,
ADD COLUMN IF NOT EXISTS password_hash text;
