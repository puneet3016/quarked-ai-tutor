from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# The exact hash I seeded for "admin" in supabase_migration.sql
hash_in_db = "$2b$12$R.Sj9u9Zk/3lI0Vp71x3lOW.8/tC.R.t0z2/WvG9BvR0b0s1l0/Wq"

# Let's check if it actually matches "quarkedadmin"
print(f"Match: {pwd_context.verify('quarkedadmin', hash_in_db)}")

# If not, let's generate a new one
new_hash = pwd_context.hash('quarkedadmin')
print(f"New Hash: {new_hash}")
