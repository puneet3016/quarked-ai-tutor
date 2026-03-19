-- ==========================================
-- QUARKED PORTAL — SUPABASE POSTGRESQL SCHEMA
-- Execute this block entirely inside the Supabase SQL Editor
-- ==========================================

-- 1. Students table
CREATE TABLE students (
  id SERIAL PRIMARY KEY,
  uuid UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
  username VARCHAR(50) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(200) NOT NULL,
  phone VARCHAR(20),
  school_id VARCHAR(50) NOT NULL,
  other_school VARCHAR(200),
  board VARCHAR(50),
  subjects TEXT[] NOT NULL DEFAULT '{}',
  approved BOOLEAN DEFAULT false,
  is_admin BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Sessions table (login tracking, questions)
CREATE TABLE sessions (
  id SERIAL PRIMARY KEY,
  session_id UUID NOT NULL,
  student_uuid UUID REFERENCES students(uuid),
  school_id VARCHAR(50),
  action VARCHAR(20) NOT NULL,  -- LOGIN, LOGOUT, QUESTION, RESPONSE
  subject VARCHAR(50),
  question_preview TEXT,
  response_length INT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Schools reference table
CREATE TABLE schools (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  city VARCHAR(100)
);

-- 4. Initial School Insertion
INSERT INTO schools (id, name, city) VALUES
  ('jpis', 'Jayshree Periwal International School', 'Jaipur'),
  ('neerja_modi', 'Neerja Modi School', 'Jaipur'),
  ('mgis', 'Maharaja Sawai Man Singh Vidyalaya', 'Jaipur'),
  ('suncity', 'Suncity School', 'Gurugram'),
  ('pathways', 'Pathways School', 'Gurugram'),
  ('scottish_high', 'Scottish High International School', 'Gurugram'),
  ('dps_intl', 'DPS International', 'Delhi'),
  ('heritage', 'The Heritage School', 'Kolkata'),
  ('oberoi_intl', 'Oberoi International School', 'Mumbai'),
  ('jamnabai', 'Jamnabai Narsee International School', 'Mumbai'),
  ('dhirubhai', 'Dhirubhai Ambani International School', 'Mumbai'),
  ('abwa', 'Aditya Birla World Academy', 'Mumbai'),
  ('symbiosis', 'Symbiosis International School', 'Pune'),
  ('other', 'Other School', '');

-- 5. Insert Admin User
-- Note: password is 'quarkedadmin', hashed with passlib bcrypt
INSERT INTO students (uuid, username, password_hash, full_name, phone, school_id, approved, is_admin)
VALUES (gen_random_uuid(), 'admin', '$2b$12$DqXb3z52Dxy0cWeuA4Q/l.Y.C8b/W8.V0sI9BvOWgL0t.6x5D1Aqi', 'Puneet Sharmma', '917011303807', 'admin', true, true);

-- 6. Insert Pre-seeded Registered Students
-- Passwords are all 'quarked2026', hashed with passlib bcrypt
INSERT INTO students (username, full_name, school_id, board, subjects, approved, password_hash) VALUES
('ahaan.k', 'Ahaan Karnawat', 'jpis', 'Cambridge IGCSE', '{"Physics", "Chemistry", "Mathematics"}', true, '$2b$12$R.Sj9u9Zk/31I0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s11O/Wq'),
('daksh.v', 'Daksh Vashisht', 'jpis', 'Cambridge IGCSE', '{"Physics", "Mathematics"}', true, '$2b$12$R.Sj9u9Zk/31I0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s11O/Wq'),
('vibhor.k', 'Vibhor Karnawat', 'jpis', 'Cambridge IGCSE', '{"Mathematics", "Computer Science"}', true, '$2b$12$R.Sj9u9Zk/31I0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s11O/Wq'),
('aheli.k', 'Aheli Karnawat', 'jpis', 'Cambridge IGCSE', '{"Business Studies", "Economics", "Add Maths", "Physics"}', true, '$2b$12$R.Sj9u9Zk/31I0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s11O/Wq'),
('aryaman', 'Aryaman', 'neerja_modi', 'Cambridge AS/A Level', '{"Physics", "Mathematics", "Computer Science"}', true, '$2b$12$R.Sj9u9Zk/31I0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s11O/Wq'),
('tanmay.h', 'Tanmay Harkawat', 'jpis', 'Cambridge AS/A Level', '{"Physics", "Mathematics"}', true, '$2b$12$R.Sj9u9Zk/31I0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s11O/Wq');

-- 7. High-Performance Indexes
CREATE INDEX idx_sessions_student ON sessions(student_uuid);
CREATE INDEX idx_sessions_school ON sessions(school_id);
CREATE INDEX idx_sessions_created ON sessions(created_at);
CREATE INDEX idx_students_school ON students(school_id);
CREATE INDEX idx_students_approved ON students(approved);
