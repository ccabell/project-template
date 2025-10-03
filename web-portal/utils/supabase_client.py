"""
Supabase client configuration for A360 Portal
Handles authentication and database operations for the internal web tool
"""

import os
from supabase import create_client, Client
from typing import Optional

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mepuegljvlnlonttanbb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseClient:
    """
    Wrapper class for Supabase operations specific to A360 Portal
    """
    
    def __init__(self):
        self.client = supabase
    
    def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        """
        Authenticate user with email and password
        Returns user data if successful, None otherwise
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return response.user if response.user else None
        except Exception as e:
            print(f"Authentication error: {e}")
            return None
    
    def create_test_user(self, email: str, projects: list, duration: str, permissions: str) -> bool:
        """
        Create a temporary test user for project collaboration
        """
        try:
            # This would create a test user record in your database
            user_data = {
                "email": email,
                "projects": projects,
                "access_duration": duration,
                "permissions": permissions,
                "created_at": "now()",
                "status": "active"
            }
            
            response = self.client.table("test_users").insert(user_data).execute()
            return len(response.data) > 0
            
        except Exception as e:
            print(f"Error creating test user: {e}")
            return False
    
    def get_project_activity(self, project_name: str) -> list:
        """
        Retrieve recent activity for a specific project
        """
        try:
            response = self.client.table("project_activity")\
                .select("*")\
                .eq("project_name", project_name)\
                .order("created_at", desc=True)\
                .limit(10)\
                .execute()
            
            return response.data
            
        except Exception as e:
            print(f"Error fetching project activity: {e}")
            return []
    
    def log_activity(self, user_email: str, action: str, project_name: str = None) -> bool:
        """
        Log user activity for audit purposes
        """
        try:
            activity_data = {
                "user_email": user_email,
                "action": action,
                "project_name": project_name,
                "timestamp": "now()"
            }
            
            response = self.client.table("user_activities").insert(activity_data).execute()
            return len(response.data) > 0
            
        except Exception as e:
            print(f"Error logging activity: {e}")
            return False
    
    def get_active_test_users(self) -> list:
        """
        Get list of currently active test users
        """
        try:
            response = self.client.table("test_users")\
                .select("*")\
                .eq("status", "active")\
                .execute()
            
            return response.data
            
        except Exception as e:
            print(f"Error fetching test users: {e}")
            return []
    
    def update_project_status(self, project_name: str, status: str, collaborator_count: int) -> bool:
        """
        Update project status and collaborator count
        """
        try:
            response = self.client.table("projects")\
                .update({
                    "status": status,
                    "collaborator_count": collaborator_count,
                    "last_updated": "now()"
                })\
                .eq("name", project_name)\
                .execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            print(f"Error updating project status: {e}")
            return False

# Global instance for use in Streamlit app
db_client = SupabaseClient()

# For backward compatibility with the original code
def get_supabase_client():
    """
    Get the Supabase client instance
    """
    return supabase