-- migration_v7_harden.sql
-- Fixes two Supabase advisories surfaced 2026-07-24:
--   (A) "RLS Policy Always True" on students / consents / consent_events / interactions / sessions
--   (B) "Function Search Path Mutable" on sync_student_active / log_consent_event (and any others)
--
-- Idempotent — safe to run more than once.

-- ===========================================================================
-- (A) Remove permissive "always true" RLS policies.
--
-- These were almost certainly auto-added when RLS was toggled on via the Supabase
-- dashboard. A USING(true) policy makes RLS allow-all, which SILENTLY RE-OPENS the
-- exposure migration_v6 closed. Quarked's access model is service-role-only (the
-- FastAPI backend uses SUPABASE_SERVICE_KEY, which bypasses RLS; no client uses the
-- anon key), so the correct state is RLS enabled with ZERO policies = deny-all to
-- anon/authenticated. Dropping these does NOT affect the backend.
--
-- SEE what exists first (run this SELECT on its own and eyeball the results):
--   SELECT tablename, policyname, roles, cmd, qual
--   FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename;
--
-- Then drop every policy in the public schema:
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public'
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I;', r.policyname, r.tablename);
  END LOOP;
END $$;

-- ===========================================================================
-- (B) Pin a stable search_path on every function in the public schema.
--
-- A mutable search_path lets a caller shadow objects a function references — a real
-- risk for SECURITY DEFINER trigger functions (sync_student_active, log_consent_event).
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT p.proname, pg_get_function_identity_arguments(p.oid) AS args
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
  LOOP
    EXECUTE format('ALTER FUNCTION public.%I(%s) SET search_path = public, pg_temp;', r.proname, r.args);
  END LOOP;
END $$;

-- ===========================================================================
-- Verify afterwards:
--   RLS on, no policies:
--     SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public';   -- all true
--     SELECT count(*) FROM pg_policies WHERE schemaname='public';               -- 0
--   Functions pinned:
--     SELECT proname, proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
--     WHERE n.nspname='public';   -- proconfig should show search_path=public, pg_temp
