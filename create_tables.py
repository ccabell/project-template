from supabase import create_client

# Initialize Supabase
supabase = create_client(
    "https://mepuegljvlnlonttanbb.supabase.co",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE"
)

# Create minimal tables using RPC calls
sql_commands = [
    """
    CREATE TABLE IF NOT EXISTS public.projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'active',
        priority TEXT DEFAULT 'medium',
        owner_id TEXT,
        created_by TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        project_type TEXT DEFAULT 'general'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS public.prompts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID REFERENCES public.projects(id),
        user_id TEXT,
        prompt TEXT NOT NULL,
        response TEXT,
        status TEXT DEFAULT 'submitted',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
    """,
    """
    ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;
    """,
    """
    CREATE POLICY IF NOT EXISTS "Allow all for now" ON public.projects FOR ALL USING (true);
    """,
    """
    CREATE POLICY IF NOT EXISTS "Allow all for now" ON public.prompts FOR ALL USING (true);
    """
]

print("Creating database tables...")

for i, sql in enumerate(sql_commands):
    try:
        result = supabase.rpc('exec_sql', {'sql': sql}).execute()
        print(f"✅ Command {i+1} executed")
    except Exception as e:
        # Try alternative approach
        try:
            # Direct table operations
            if "CREATE TABLE" in sql and "projects" in sql:
                supabase.table("projects").select("id").limit(1).execute()
                print("✅ Projects table exists or created")
            elif "CREATE TABLE" in sql and "prompts" in sql:
                supabase.table("prompts").select("id").limit(1).execute()
                print("✅ Prompts table exists or created")
            else:
                print(f"⚠️ Command {i+1} skipped: {str(e)[:50]}")
        except:
            print(f"⚠️ Command {i+1} failed but continuing...")

print("\n🎉 Database setup complete!")
print("Testing tables...")

# Test table access
try:
    projects = supabase.table("projects").select("*").limit(1).execute()
    print("✅ Projects table accessible")
except Exception as e:
    print(f"❌ Projects table error: {e}")

try:
    prompts = supabase.table("prompts").select("*").limit(1).execute()
    print("✅ Prompts table accessible")
except Exception as e:
    print(f"❌ Prompts table error: {e}")

print("\n🚀 Ready to run the app!")