-- migration_v6_enable_rls.sql
-- Fixes Supabase "rls_disabled_in_public" security alert (2026-07-12).
--
-- WHY: Tables in the public schema without Row-Level Security are exposed through
-- Supabase's auto-generated REST API to anyone holding the project's anon key. These
-- tables hold minors' PII (students, parent contacts, password hashes, consents,
-- encrypted questions), so this is a DPDP-grade exposure and must be closed.
--
-- WHY IT'S SAFE: the Quarked backend connects with the SERVICE ROLE key
-- (SUPABASE_SERVICE_KEY), which has BYPASSRLS — it ignores RLS entirely and keeps
-- working. No browser/client uses the anon key (the React portal has zero direct
-- Supabase calls; all DB access goes through the FastAPI backend). Enabling RLS with
-- NO policies therefore denies anonymous/public access while leaving the app untouched.
--
-- Idempotent — safe to run more than once.

-- 1. Enable RLS on every table in the public schema.
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', r.tablename);
  END LOOP;
END $$;

-- 2. Verify: every table should now show rowsecurity = true.
--    (Run this SELECT separately and eyeball the results.)
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- NOTE: We intentionally add NO policies. With RLS enabled and no policy, the anon and
-- authenticated roles get deny-all; only the service_role (backend) can read/write.
-- Do NOT add a permissive "allow all" policy — that would re-open the exposure.

-- ---------------------------------------------------------------------------
-- 3. Fix Supabase "Security Definer View" alert on public.monthly_spend_usd
--    (added 2026-07-24).
--
-- WHY: the view sums cost_usd from `interactions`. As a SECURITY DEFINER view it runs
-- with the creator's privileges and can bypass the RLS enabled above, leaking spend
-- totals to the anon/public role. Flipping it to SECURITY INVOKER makes it respect the
-- querying role's RLS. The backend uses the service_role key (BYPASSRLS), so it keeps
-- reading the view fine; anon/public gets nothing.
ALTER VIEW public.monthly_spend_usd SET (security_invoker = on);

-- Belt-and-suspenders: only the backend (service_role) needs this view, so remove the
-- public API roles' access entirely. service_role is unaffected.
REVOKE ALL ON public.monthly_spend_usd FROM anon, authenticated;
