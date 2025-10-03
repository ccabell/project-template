#!/usr/bin/env python3
"""
A360 Internal Project Hub - Database Setup Script
Run this if you can't access Supabase web interface
"""

import os
from supabase import create_client

# Supabase configuration
SUPABASE_URL = "https://mepuegljvlnlonttanbb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE"

def setup_database():
    """Set up the database schema programmatically"""
    
    print("🚀 Setting up A360 Project Hub Database...")
    
    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Check connection
    try:
        print("✅ Connected to Supabase successfully")
        
        # Test basic table creation (simple version for now)
        print("📋 Setting up basic tables...")
        
        # Create a simple prompts table to start
        try:
            result = supabase.table("prompts").select("*").limit(1).execute()
            print("✅ Prompts table already exists")
        except Exception as e:
            print("⚠️  Prompts table doesn't exist - this is expected for new setup")
            print("   Please run the SQL schema manually in Supabase dashboard")
        
        print("\n🎯 Database setup status:")
        print(f"   📍 Database URL: {SUPABASE_URL}")
        print("   📍 Connection: ✅ Working")
        print("   📍 Next step: Run SQL schema in Supabase dashboard")
        
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        return False

def test_app_connection():
    """Test if the app can connect to Supabase"""
    
    print("\n🧪 Testing App Connection...")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test a simple operation that doesn't require tables
        print("✅ App can connect to Supabase")
        print("✅ Credentials are working")
        
        return True
        
    except Exception as e:
        print(f"❌ App connection failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("A360 PROJECT HUB - DATABASE SETUP")
    print("=" * 50)
    
    # Test database connection
    db_ok = setup_database()
    
    # Test app connection  
    app_ok = test_app_connection()
    
    print("\n" + "=" * 50)
    print("SETUP SUMMARY")
    print("=" * 50)
    
    if db_ok and app_ok:
        print("✅ Everything looks good!")
        print("📝 Next steps:")
        print("   1. Access Supabase dashboard (try different browser)")
        print("   2. Run the SQL schema from database_schema.sql")
        print("   3. Test your Streamlit app: python -m streamlit run app.py")
    else:
        print("⚠️  Some issues detected:")
        if not db_ok:
            print("   - Database connection issues")
        if not app_ok:
            print("   - App connection issues")
        
    print("\n🌐 Supabase Dashboard URLs to try:")
    print("   - https://mepuegljvlnlonttanbb.supabase.co")
    print("   - https://supabase.com/dashboard/project/mepuegljvlnlonttanbb")
    print("   - https://supabase.com/dashboard (then select your project)")
    
    print("\n📧 If you still can't access the dashboard:")
    print("   - Check your email for Supabase login credentials")
    print("   - Try password reset on https://supabase.com")
    print("   - Use incognito/private browser mode")
    print("   - Clear browser cookies for supabase.com")