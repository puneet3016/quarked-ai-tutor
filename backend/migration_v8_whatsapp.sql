-- migration_v8_whatsapp.sql
-- Stores inbound WhatsApp messages + outbound delivery statuses from the Cloud API webhook.
--
-- WHY: a Cloud API number has no inbox app. Incoming messages arrive ONLY as webhook
-- POSTs. With no webhook deployed, 26 inbound messages (28 Jun–25 Jul 2026) were counted
-- by Meta and lost. This table is where they land from now on.
--
-- Delivery statuses (sent/delivered/read/FAILED + reason) also arrive on the same webhook,
-- which is how we finally see why outbound messages aren't reaching handsets.
--
-- Idempotent — safe to run more than once.

-- Inbound messages from people messaging the business number.
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id           bigserial PRIMARY KEY,
    wa_message_id text UNIQUE,              -- Meta's wamid, for dedupe on webhook retries
    from_number  text        NOT NULL,      -- sender's wa_id
    profile_name text,                      -- WhatsApp display name, if provided
    msg_type     text,                      -- text | image | audio | document | ...
    body         text,                      -- text body or image caption
    media_id     text,                      -- if the message carried media
    received_at  timestamptz NOT NULL DEFAULT now(),
    handled      boolean     NOT NULL DEFAULT false,  -- mark true once you've replied
    raw          jsonb                      -- full payload, so nothing is ever lost again
);

-- Outbound replies are stored in the same table so a thread shows both sides.
-- ADD COLUMN IF NOT EXISTS keeps this safe to re-run if you already applied v8.
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS direction text NOT NULL DEFAULT 'in';
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS to_number text;

CREATE INDEX IF NOT EXISTS idx_wa_messages_received  ON whatsapp_messages (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_wa_messages_handled   ON whatsapp_messages (handled, received_at DESC);
-- 'contact' = the other party, whichever direction the message went. Powers the thread view.
CREATE INDEX IF NOT EXISTS idx_wa_messages_from      ON whatsapp_messages (from_number, received_at DESC);

-- Outbound delivery receipts: this is what tells us WHY a send never arrives.
CREATE TABLE IF NOT EXISTS whatsapp_statuses (
    id            bigserial PRIMARY KEY,
    wa_message_id text,                     -- the wamid returned when we sent
    recipient     text,
    status        text,                     -- sent | delivered | read | failed
    error_code    text,
    error_title   text,
    error_detail  text,
    occurred_at   timestamptz NOT NULL DEFAULT now(),
    raw           jsonb
);

CREATE INDEX IF NOT EXISTS idx_wa_statuses_occurred ON whatsapp_statuses (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_wa_statuses_msgid    ON whatsapp_statuses (wa_message_id);

-- Same lockdown as every other table: RLS on, NO policies. Only the service_role
-- (the FastAPI backend) can read/write; anon/authenticated are denied.
ALTER TABLE whatsapp_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_statuses ENABLE ROW LEVEL SECURITY;
