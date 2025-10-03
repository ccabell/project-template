import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import uuid
import pandas as pd
import json
import io
import base64
from typing import Dict, List, Optional, Any
import docx
import PyPDF2
import requests

# Page configuration
st.set_page_config(
    page_title="A360 Internal Project Hub",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
    except:
        # Fallback for local development
        supabase_url = "https://mepuegljvlnlonttanbb.supabase.co"
        supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE"
    
    return create_client(supabase_url, supabase_key)

supabase = init_supabase()

# Authentication functions
def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            st.session_state.user = response.user
            st.session_state.logged_in = True
            
            # Get or create user profile
            profile = get_user_profile(response.user.id)
            st.session_state.user_profile = profile
            
            return True, "Login successful!"
    except Exception as e:
        return False, f"Login failed: {str(e)}"
    return False, "Invalid credentials"

def signup_user(email, password, full_name):
    try:
        response = supabase.auth.sign_up({
            "email": email, 
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name
                }
            }
        })
        if response.user:
            return True, "Account created successfully! Please check your email to confirm."
    except Exception as e:
        return False, f"Signup failed: {str(e)}"
    return False, "Signup failed"

def logout_user():
    try:
        supabase.auth.sign_out()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    except:
        pass

# User profile functions
def get_user_profile(user_id: str) -> Dict:
    """Get or create user profile"""
    try:
        result = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        if result.data:
            return result.data[0]
        else:
            # Create profile if it doesn't exist
            profile_data = {
                "id": user_id,
                "email": st.session_state.user.email if hasattr(st.session_state, 'user') else "",
                "role": "external"  # Default role
            }
            result = supabase.table("user_profiles").insert(profile_data).execute()
            return result.data[0] if result.data else profile_data
    except Exception as e:
        st.error(f"Error getting user profile: {str(e)}")
        return {"id": user_id, "role": "external", "email": ""}

def get_accessible_projects(user_id: str, user_role: str) -> List[Dict]:
    """Get projects accessible to the user based on role and sharing permissions"""
    try:
        if user_role == "admin":
            # Admins see all projects
            result = supabase.table("projects").select("*").execute()
        elif user_role == "internal":
            # Internal users see shared projects and their own
            result = supabase.table("projects").select("*").or_("is_shared.eq.true,created_by.eq." + user_id).execute()
        else:
            # External users see only shared projects and explicitly granted access
            result = supabase.table("projects").select("*").eq("is_shared", True).execute()
        
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error loading projects: {str(e)}")
        return []

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None
if 'current_project' not in st.session_state:
    st.session_state.current_project = None
if 'project_view' not in st.session_state:
    st.session_state.project_view = 'menu'

# Authentication UI
def show_auth():
    st.title("🏢 A360 Internal Project Hub")
    st.markdown("### Welcome to your internal project management system")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to your account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary", key="login_btn"):
            if email and password:
                success, message = login_user(email, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.warning("Please enter both email and password")
    
    with tab2:
        st.subheader("Create new account")
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        full_name = st.text_input("Full Name", key="signup_name")
        
        if st.button("Sign Up", type="primary", key="signup_btn"):
            if new_email and new_password and confirm_password and full_name:
                if new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = signup_user(new_email, new_password, full_name)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            else:
                st.warning("Please fill in all fields")

# Project Menu - Main Dashboard
def show_project_menu():
    st.title("📊 Project Dashboard")
    
    # User info and logout
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        profile = st.session_state.user_profile
        st.markdown(f"**Welcome, {profile.get('full_name', profile.get('email', 'User'))}!**")
        st.caption(f"Role: {profile.get('role', 'external').title()} | {profile.get('email', '')}")
    
    with col3:
        if st.button("🚪 Logout", key="logout_btn"):
            logout_user()
    
    st.divider()
    
    # Load accessible projects
    user_id = st.session_state.user.id
    user_role = st.session_state.user_profile.get('role', 'external')
    projects = get_accessible_projects(user_id, user_role)
    
    if projects:
        st.subheader("Available Projects")
        
        # Create project cards in a grid
        cols = st.columns(3)
        for i, project in enumerate(projects):
            with cols[i % 3]:
                with st.container():
                    st.markdown(f"### {project['name']}")
                    st.markdown(f"**Type:** {project['project_type'].replace('_', ' ').title()}")
                    st.markdown(f"**Description:** {project['description'][:100]}...")
                    
                    # Status indicators
                    col_status, col_shared = st.columns(2)
                    with col_status:
                        status_color = "🟢" if project['status'] == 'active' else "🟡"
                        st.markdown(f"{status_color} {project['status'].title()}")
                    with col_shared:
                        if project.get('is_shared'):
                            st.markdown("🔗 Shared")
                        else:
                            st.markdown("🔒 Private")
                    
                    # Open project button
                    if st.button(f"Open {project['name']}", key=f"open_{project['id']}", type="primary"):
                        st.session_state.current_project = project
                        st.session_state.project_view = project['project_type']
                        st.rerun()
                    
                    st.markdown("---")
    else:
        st.info("No projects available. Contact your administrator for access.")
    
    # Admin controls
    if user_role == "admin":
        st.divider()
        show_admin_controls()

def show_admin_controls():
    """Admin interface for managing projects and users"""
    st.subheader("🔧 Admin Controls")
    
    tab1, tab2 = st.tabs(["Manage Projects", "Manage Users"])
    
    with tab1:
        st.markdown("#### Project Management")
        
        # Create new project
        with st.expander("Create New Project"):
            new_name = st.text_input("Project Name")
            new_desc = st.text_area("Description")
            new_type = st.selectbox("Project Type", 
                ["transcript_generator", "prompt_tester", "transcript_analyzer", "general"])
            is_shared = st.checkbox("Share with external users")
            
            if st.button("Create Project"):
                try:
                    project_data = {
                        "name": new_name,
                        "description": new_desc,
                        "project_type": new_type,
                        "is_shared": is_shared,
                        "created_by": st.session_state.user.id
                    }
                    result = supabase.table("projects").insert(project_data).execute()
                    st.success(f"Project '{new_name}' created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating project: {str(e)}")
        
        # Manage existing projects
        projects = supabase.table("projects").select("*").execute().data or []
        if projects:
            st.markdown("#### Existing Projects")
            for project in projects:
                with st.expander(f"{project['name']} ({project['project_type']})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Description:** {project['description']}")
                        st.markdown(f"**Status:** {project['status']}")
                        st.markdown(f"**Shared:** {'Yes' if project.get('is_shared') else 'No'}")
                    with col2:
                        # Toggle sharing
                        current_shared = project.get('is_shared', False)
                        if st.button(f"{'Unshare' if current_shared else 'Share'}", 
                                   key=f"toggle_share_{project['id']}"):
                            try:
                                supabase.table("projects").update({
                                    "is_shared": not current_shared
                                }).eq("id", project['id']).execute()
                                st.success("Project sharing updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating project: {str(e)}")
    
    with tab2:
        st.markdown("#### User Management")
        try:
            users = supabase.table("user_profiles").select("*").execute().data or []
            if users:
                for user in users:
                    with st.expander(f"{user.get('full_name', user.get('email', 'Unknown'))} - {user.get('role', 'external').title()}"):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**Email:** {user.get('email', 'N/A')}")
                            st.markdown(f"**Current Role:** {user.get('role', 'external').title()}")
                        with col2:
                            new_role = st.selectbox("Change Role", 
                                ["external", "internal", "admin"], 
                                index=["external", "internal", "admin"].index(user.get('role', 'external')),
                                key=f"role_{user['id']}")
                            if st.button("Update Role", key=f"update_{user['id']}"):
                                try:
                                    supabase.table("user_profiles").update({
                                        "role": new_role
                                    }).eq("id", user['id']).execute()
                                    st.success("User role updated!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error updating user: {str(e)}")
        except Exception as e:
            st.error(f"Error loading users: {str(e)}")

# Project 1: Transcript Generation Tool
def show_transcript_generator():
    project = st.session_state.current_project
    st.title(f"🎯 {project['name']}")
    st.markdown(project['description'])
    
    # Back button
    if st.button("← Back to Menu", key="back_to_menu_1"):
        st.session_state.project_view = 'menu'
        st.session_state.current_project = None
        st.rerun()
    
    st.divider()
    
    tab1, tab2 = st.tabs(["Generate Transcript", "View Generated"])
    
    with tab1:
        st.subheader("Generate Synthetic Transcript")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Form inputs
            patient_name = st.text_input("Patient Name (or leave blank for synthetic)")
            patient_dob = st.date_input("Patient Date of Birth (optional)", value=None)
            provider = st.text_input("Provider Name", value="Dr. Smith")
            specialty = st.selectbox("Specialty", ["Medspa", "Explant", "Venous"])
            visit_type = st.selectbox("Visit Type", 
                ["Initial Consultation", "Follow-up", "Treatment", "Post-Treatment"])
            is_series = st.checkbox("Part of treatment series?")
        
        with col2:
            st.markdown("#### Generation Options")
            complexity = st.slider("Content Complexity", 1, 5, 3)
            length = st.selectbox("Transcript Length", ["Short (5-10 min)", "Medium (15-20 min)", "Long (30+ min)"])
            focus_areas = st.multiselect("Focus Areas", 
                ["Patient concerns", "Side effects", "Treatment options", "Cost discussion", "Follow-up care"])
        
        # Generate button
        if st.button("🚀 Generate Transcript", type="primary"):
            with st.spinner("Generating synthetic transcript..."):
                # This would integrate with Warp AI/N8N workflow
                # For now, we'll create a mock transcript
                mock_content = generate_mock_transcript(
                    patient_name or "Patient X", 
                    specialty, 
                    visit_type, 
                    complexity,
                    focus_areas
                )
                
                # Save to database
                try:
                    transcript_data = {
                        "patient_name": patient_name or "Synthetic Patient",
                        "patient_dob": patient_dob.isoformat() if patient_dob else None,
                        "provider": provider,
                        "specialty": specialty,
                        "visit_type": visit_type,
                        "is_series": is_series,
                        "content": mock_content,
                        "created_by": st.session_state.user.id,
                        "metadata": {
                            "complexity": complexity,
                            "length": length,
                            "focus_areas": focus_areas,
                            "generated": True
                        }
                    }
                    
                    result = supabase.table("transcripts").insert(transcript_data).execute()
                    
                    if result.data:
                        st.success("✅ Transcript generated successfully!")
                        st.subheader("Generated Transcript")
                        st.text_area("Content", mock_content, height=300, disabled=True)
                        
                        # Download option
                        st.download_button(
                            "📄 Download Transcript",
                            mock_content,
                            file_name=f"transcript_{specialty}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain"
                        )
                    else:
                        st.error("Failed to save transcript")
                        
                except Exception as e:
                    st.error(f"Error generating transcript: {str(e)}")
    
    with tab2:
        st.subheader("Generated Transcripts")
        try:
            # Load user's generated transcripts
            result = supabase.table("transcripts").select("*").eq("created_by", st.session_state.user.id).order("created_at", desc=True).execute()
            
            if result.data:
                for transcript in result.data:
                    with st.expander(f"{transcript['specialty']} - {transcript['patient_name']} ({transcript['created_at'][:10]})"):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**Provider:** {transcript['provider']}")
                            st.markdown(f"**Visit Type:** {transcript['visit_type']}")
                            st.markdown(f"**Series:** {'Yes' if transcript['is_series'] else 'No'}")
                        with col2:
                            if st.button(f"View Full Content", key=f"view_{transcript['id']}"):
                                st.text_area("Full Transcript", transcript['content'], height=400, disabled=True)
            else:
                st.info("No transcripts generated yet. Use the Generate tab to create your first transcript.")
                
        except Exception as e:
            st.error(f"Error loading transcripts: {str(e)}")

# Project 2: Prompt Testing Tool
def show_prompt_tester():
    project = st.session_state.current_project
    st.title(f"🧪 {project['name']}")
    st.markdown(project['description'])
    
    # Back button
    if st.button("← Back to Menu", key="back_to_menu_2"):
        st.session_state.project_view = 'menu'
        st.session_state.current_project = None
        st.rerun()
    
    st.divider()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Upload Transcript", "Prompt Library", "Run Tests", "Results Dashboard"])
    
    with tab1:
        show_transcript_upload()
    
    with tab2:
        show_prompt_library()
    
    with tab3:
        show_test_runner()
    
    with tab4:
        show_results_dashboard()

def show_transcript_upload():
    """Handle transcript file uploads"""
    st.subheader("📁 Upload Transcript")
    
    uploaded_file = st.file_uploader(
        "Choose a transcript file",
        type=['txt', 'docx', 'pdf'],
        help="Supported formats: TXT, DOCX, PDF (max 10MB)"
    )
    
    description = st.text_area("Description (optional)", placeholder="Enter a description for this transcript...")
    
    if uploaded_file is not None:
        # File information
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("File Type", uploaded_file.type)
        
        # Process file
        content = extract_text_from_file(uploaded_file)
        
        if content:
            # Show preview
            st.subheader("Content Preview")
            preview = content[:1000] + ("..." if len(content) > 1000 else "")
            st.text_area("Preview", preview, height=200, disabled=True)
            
            # Save button
            if st.button("💾 Save Transcript", type="primary"):
                # In a real implementation, we'd save to the tests table or create a uploads table
                st.success("✅ Transcript uploaded successfully!")
                st.info("This transcript can now be used in the Run Tests tab.")

def show_prompt_library():
    """Manage prompt templates"""
    st.subheader("📚 Prompt Library")
    
    tab_manage, tab_create = st.tabs(["Manage Prompts", "Create New"])
    
    with tab_manage:
        try:
            result = supabase.table("prompts").select("*").order("created_at", desc=True).execute()
            prompts = result.data or []
            
            if prompts:
                for prompt in prompts:
                    with st.expander(f"{prompt['title']} ({prompt.get('category', 'uncategorized')})"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**Content:** {prompt['content']}")
                            if prompt.get('variables'):
                                vars_list = json.loads(prompt['variables']) if isinstance(prompt['variables'], str) else prompt['variables']
                                st.markdown(f"**Variables:** {', '.join(vars_list) if vars_list else 'None'}")
                            st.markdown(f"**Template:** {'Yes' if prompt.get('is_template') else 'No'}")
                        with col2:
                            if st.button("Use Prompt", key=f"use_{prompt['id']}"):
                                st.session_state[f"selected_prompt_{prompt['id']}"] = prompt
                                st.success("Prompt selected! Go to Run Tests tab.")
            else:
                st.info("No prompts found. Create your first prompt in the Create New tab.")
                
        except Exception as e:
            st.error(f"Error loading prompts: {str(e)}")
    
    with tab_create:
        st.markdown("#### Create New Prompt")
        
        title = st.text_input("Prompt Title")
        content = st.text_area("Prompt Content", height=150)
        category = st.selectbox("Category", ["summary", "analysis", "extraction", "comparison", "other"])
        variables = st.text_input("Variables (comma-separated)", help="e.g., patient_name, specialty, treatment_focus")
        is_template = st.checkbox("Make this a template")
        
        if st.button("💾 Save Prompt", type="primary"):
            if title and content:
                try:
                    var_list = [v.strip() for v in variables.split(",") if v.strip()] if variables else []
                    prompt_data = {
                        "title": title,
                        "content": content,
                        "category": category,
                        "variables": json.dumps(var_list),
                        "is_template": is_template,
                        "created_by": st.session_state.user.id
                    }
                    
                    result = supabase.table("prompts").insert(prompt_data).execute()
                    st.success("✅ Prompt saved successfully!")
                    
                except Exception as e:
                    st.error(f"Error saving prompt: {str(e)}")
            else:
                st.warning("Please provide both title and content")

def show_test_runner():
    """Run prompts against transcripts"""
    st.subheader("🚀 Run Tests")
    
    # Select transcript (this would come from uploaded transcripts or database)
    st.markdown("#### Select Transcript")
    sample_transcripts = ["Sample Medspa Transcript", "Sample Explant Consultation", "Sample Venous Treatment"]
    selected_transcript = st.selectbox("Choose transcript", sample_transcripts)
    
    # Select prompt
    st.markdown("#### Select Prompt")
    try:
        result = supabase.table("prompts").select("*").execute()
        prompts = result.data or []
        
        if prompts:
            prompt_options = {f"{p['title']} ({p.get('category', 'uncategorized')})": p for p in prompts}
            selected_prompt_key = st.selectbox("Choose prompt", list(prompt_options.keys()))
            selected_prompt = prompt_options[selected_prompt_key]
            
            # Show prompt content
            st.markdown("**Prompt Content:**")
            st.text_area("", selected_prompt['content'], height=100, disabled=True)
            
            # Variable substitution
            variables = json.loads(selected_prompt['variables']) if selected_prompt.get('variables') else []
            variable_values = {}
            
            if variables:
                st.markdown("#### Fill Variables")
                for var in variables:
                    variable_values[var] = st.text_input(f"Value for {var}", key=f"var_{var}")
            
            # Run test
            if st.button("🎯 Run Test", type="primary"):
                with st.spinner("Running test..."):
                    # Mock test execution
                    result_content = f"Test executed for prompt '{selected_prompt['title']}' on transcript '{selected_transcript}'"
                    if variable_values:
                        result_content += f"\nVariable substitutions: {variable_values}"
                    
                    # Mock AI response
                    mock_result = generate_mock_prompt_result(selected_prompt['title'], selected_transcript)
                    
                    st.success("✅ Test completed!")
                    st.subheader("Results")
                    st.markdown(mock_result)
                    
                    # Save test result (in real implementation)
                    try:
                        test_data = {
                            "prompt_id": selected_prompt['id'],
                            "test_name": f"Test_{selected_prompt['title']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            "variables_filled": json.dumps(variable_values),
                            "status": "completed",
                            "created_by": st.session_state.user.id
                        }
                        
                        test_result = supabase.table("tests").insert(test_data).execute()
                        
                        if test_result.data:
                            result_data = {
                                "test_id": test_result.data[0]['id'],
                                "output": mock_result,
                                "execution_time_ms": 2500,
                                "model_used": "mock-model-v1",
                                "tokens_used": 150
                            }
                            supabase.table("results").insert(result_data).execute()
                            
                    except Exception as e:
                        st.warning(f"Result saved locally: {str(e)}")
        
        else:
            st.warning("No prompts available. Create prompts in the Prompt Library tab first.")
            
    except Exception as e:
        st.error(f"Error loading prompts: {str(e)}")

def show_results_dashboard():
    """Display test results with comparison"""
    st.subheader("📊 Results Dashboard")
    
    try:
        # Load test results
        result = supabase.table("results").select("*, tests(*, prompts(title))").order("created_at", desc=True).execute()
        results = result.data or []
        
        if results:
            st.markdown("#### Recent Test Results")
            
            # Results comparison
            if len(results) > 1:
                st.markdown("#### Compare Results")
                compare_results = st.multiselect(
                    "Select results to compare (max 3)",
                    [f"{r['tests']['prompts']['title']} - {r['created_at'][:16]}" for r in results[:10]],
                    max_selections=3
                )
                
                if compare_results:
                    cols = st.columns(len(compare_results))
                    for i, result_name in enumerate(compare_results):
                        result_index = next(j for j, r in enumerate(results) 
                                          if f"{r['tests']['prompts']['title']} - {r['created_at'][:16]}" == result_name)
                        result_data = results[result_index]
                        
                        with cols[i]:
                            st.markdown(f"**{result_data['tests']['prompts']['title']}**")
                            st.markdown(f"Execution: {result_data['execution_time_ms']}ms")
                            st.markdown(f"Tokens: {result_data.get('tokens_used', 'N/A')}")
                            st.text_area("Output", result_data['output'][:200] + "...", height=150, disabled=True, key=f"compare_{i}")
            
            # Individual results
            st.markdown("#### All Results")
            for result_item in results:
                with st.expander(f"{result_item['tests']['prompts']['title']} - {result_item['created_at'][:16]}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.text_area("Full Output", result_item['output'], height=200, disabled=True)
                    with col2:
                        st.metric("Execution Time", f"{result_item['execution_time_ms']}ms")
                        st.metric("Model Used", result_item.get('model_used', 'N/A'))
                        st.metric("Tokens Used", result_item.get('tokens_used', 'N/A'))
                        
                        # Export individual result
                        if st.button("📄 Export", key=f"export_{result_item['id']}"):
                            export_data = {
                                "prompt": result_item['tests']['prompts']['title'],
                                "output": result_item['output'],
                                "timestamp": result_item['created_at'],
                                "execution_time_ms": result_item['execution_time_ms']
                            }
                            st.download_button(
                                "Download JSON",
                                json.dumps(export_data, indent=2),
                                file_name=f"test_result_{result_item['id']}.json",
                                mime="application/json"
                            )
        else:
            st.info("No test results yet. Run some tests first!")
            
    except Exception as e:
        st.error(f"Error loading results: {str(e)}")

# Project 3: Transcript Analysis Interface
def show_transcript_analyzer():
    project = st.session_state.current_project
    st.title(f"🔍 {project['name']}")
    st.markdown(project['description'])
    
    # Back button
    if st.button("← Back to Menu", key="back_to_menu_3"):
        st.session_state.project_view = 'menu'
        st.session_state.current_project = None
        st.rerun()
    
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["Transcript Database", "Run Analysis", "Export Results"])
    
    with tab1:
        show_transcript_database()
    
    with tab2:
        show_analysis_runner()
    
    with tab3:
        show_export_interface()

def show_transcript_database():
    """Manage the database of analysis transcripts"""
    st.subheader("🗂️ Transcript Database")
    
    # Upload new analysis transcript
    with st.expander("Upload New Analysis Transcript"):
        uploaded_file = st.file_uploader("Choose transcript file", type=['txt', 'docx', 'pdf'])
        specialty = st.selectbox("Specialty", ["Medspa", "Explant", "Venous", "Other"])
        date_recorded = st.date_input("Date Recorded (if known)", value=None)
        keywords = st.text_input("Keywords (comma-separated)", help="e.g., botox, side effects, consultation")
        
        if uploaded_file and st.button("📤 Upload Transcript"):
            content = extract_text_from_file(uploaded_file)
            if content:
                try:
                    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
                    transcript_data = {
                        "file_name": uploaded_file.name,
                        "content": content,
                        "specialty": specialty,
                        "date_recorded": date_recorded.isoformat() if date_recorded else None,
                        "keywords": keyword_list,
                        "uploaded_by": st.session_state.user.id,
                        "metadata": {
                            "file_size": uploaded_file.size,
                            "upload_date": datetime.now().isoformat()
                        }
                    }
                    
                    result = supabase.table("analysis_transcripts").insert(transcript_data).execute()
                    st.success("✅ Transcript uploaded successfully!")
                    
                except Exception as e:
                    st.error(f"Error uploading transcript: {str(e)}")
    
    # Show existing transcripts
    try:
        result = supabase.table("analysis_transcripts").select("*").order("created_at", desc=True).execute()
        transcripts = result.data or []
        
        if transcripts:
            st.subheader("Available Transcripts")
            
            # Search and filter
            col1, col2, col3 = st.columns(3)
            with col1:
                search_term = st.text_input("🔍 Search", placeholder="Search in filename or keywords...")
            with col2:
                filter_specialty = st.selectbox("Filter by Specialty", ["All"] + ["Medspa", "Explant", "Venous", "Other"])
            with col3:
                filter_date = st.date_input("Filter by Date", value=None)
            
            # Apply filters
            filtered_transcripts = transcripts
            if search_term:
                filtered_transcripts = [t for t in filtered_transcripts 
                                     if search_term.lower() in t['file_name'].lower() 
                                     or any(search_term.lower() in kw.lower() for kw in (t.get('keywords') or []))]
            
            if filter_specialty != "All":
                filtered_transcripts = [t for t in filtered_transcripts if t.get('specialty') == filter_specialty]
            
            if filter_date:
                filtered_transcripts = [t for t in filtered_transcripts 
                                     if t.get('date_recorded') and t['date_recorded'][:10] == filter_date.isoformat()]
            
            # Display transcripts
            st.markdown(f"**Found {len(filtered_transcripts)} transcripts**")
            
            for transcript in filtered_transcripts:
                with st.expander(f"{transcript['file_name']} ({transcript.get('specialty', 'Unknown')})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Specialty:** {transcript.get('specialty', 'N/A')}")
                        st.markdown(f"**Date Recorded:** {transcript.get('date_recorded', 'N/A')}")
                        if transcript.get('keywords'):
                            st.markdown(f"**Keywords:** {', '.join(transcript['keywords'])}")
                        st.markdown(f"**Uploaded:** {transcript['created_at'][:10]}")
                    with col2:
                        if st.button("👁️ Preview", key=f"preview_{transcript['id']}"):
                            preview = transcript['content'][:500] + ("..." if len(transcript['content']) > 500 else "")
                            st.text_area("Content Preview", preview, height=150, disabled=True)
        else:
            st.info("No transcripts in database. Upload some transcripts to get started.")
            
    except Exception as e:
        st.error(f"Error loading transcripts: {str(e)}")

def show_analysis_runner():
    """Run analysis queries across multiple transcripts"""
    st.subheader("🎯 Run Analysis")
    
    # Load available transcripts
    try:
        result = supabase.table("analysis_transcripts").select("id, file_name, specialty").execute()
        transcripts = result.data or []
        
        if transcripts:
            # Query input
            st.markdown("#### Analysis Query")
            query_examples = [
                "Find all mentions of Xeomin side effects",
                "Summarize recurring concerns in Venous transcripts",
                "Extract cost discussions across all consultations",
                "Identify patient satisfaction indicators",
                "Find mentions of competitor treatments"
            ]
            
            selected_example = st.selectbox("Use example query:", ["Custom query..."] + query_examples)
            
            if selected_example == "Custom query...":
                analysis_query = st.text_area("Enter your analysis query", height=100)
            else:
                analysis_query = st.text_area("Enter your analysis query", value=selected_example, height=100)
            
            # Transcript selection
            st.markdown("#### Select Transcripts")
            transcript_options = {f"{t['file_name']} ({t.get('specialty', 'Unknown')})": t['id'] for t in transcripts}
            
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_transcripts = st.multiselect(
                    "Choose transcripts to analyze",
                    list(transcript_options.keys()),
                    help="Select one or more transcripts for analysis"
                )
            with col2:
                # Quick select options
                if st.button("Select All Medspa"):
                    selected_transcripts = [k for k, v in transcript_options.items() if "Medspa" in k]
                if st.button("Select All"):
                    selected_transcripts = list(transcript_options.keys())
                if st.button("Clear Selection"):
                    selected_transcripts = []
            
            # Run analysis
            if st.button("🚀 Run Analysis", type="primary", disabled=not analysis_query or not selected_transcripts):
                with st.spinner("Running analysis across selected transcripts..."):
                    # Mock analysis
                    selected_ids = [transcript_options[t] for t in selected_transcripts]
                    mock_results = generate_mock_analysis_results(analysis_query, selected_transcripts)
                    
                    # Save results
                    try:
                        analysis_data = {
                            "query": analysis_query,
                            "transcript_ids": selected_ids,
                            "results": mock_results,
                            "created_by": st.session_state.user.id,
                            "result_count": len(selected_transcripts)
                        }
                        
                        result = supabase.table("analysis_results").insert(analysis_data).execute()
                        
                        st.success("✅ Analysis completed!")
                        st.subheader("Analysis Results")
                        
                        # Display results
                        for i, (transcript_name, result_text) in enumerate(zip(selected_transcripts, mock_results['individual_results'])):
                            with st.expander(f"Results for: {transcript_name}"):
                                st.markdown(result_text)
                        
                        # Summary
                        if mock_results.get('summary'):
                            st.subheader("Summary Across All Transcripts")
                            st.markdown(mock_results['summary'])
                        
                    except Exception as e:
                        st.error(f"Error saving analysis results: {str(e)}")
                        # Still show results even if saving failed
                        st.subheader("Analysis Results")
                        st.json(mock_results)
        
        else:
            st.warning("No transcripts available for analysis. Upload transcripts first in the Transcript Database tab.")
            
    except Exception as e:
        st.error(f"Error loading transcripts for analysis: {str(e)}")

def show_export_interface():
    """Export analysis results"""
    st.subheader("📤 Export Results")
    
    try:
        # Load analysis results
        result = supabase.table("analysis_results").select("*").order("created_at", desc=True).execute()
        analyses = result.data or []
        
        if analyses:
            st.markdown("#### Available Analysis Results")
            
            for analysis in analyses:
                with st.expander(f"Query: {analysis['query'][:60]}... ({analysis['created_at'][:10]})"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Query:** {analysis['query']}")
                        st.markdown(f"**Transcripts Analyzed:** {analysis['result_count']}")
                        st.markdown(f"**Analysis Date:** {analysis['created_at'][:16]}")
                    
                    with col2:
                        # Export options
                        export_format = st.selectbox(
                            "Export Format",
                            ["JSON", "CSV", "Excel"],
                            key=f"format_{analysis['id']}"
                        )
                        
                        if st.button("📄 Export", key=f"export_analysis_{analysis['id']}"):
                            export_analysis_results(analysis, export_format)
        
        else:
            st.info("No analysis results available. Run some analyses first!")
            
    except Exception as e:
        st.error(f"Error loading analysis results: {str(e)}")

# Helper functions
def generate_mock_transcript(patient_name: str, specialty: str, visit_type: str, complexity: int, focus_areas: List[str]) -> str:
    """Generate mock transcript content"""
    base_content = f"""CONSULTATION TRANSCRIPT
Patient: {patient_name}
Specialty: {specialty}
Visit Type: {visit_type}
Date: {datetime.now().strftime('%Y-%m-%d')}

Dr. Smith: Good morning, {patient_name}. How are you feeling today?

Patient: Good morning, Doctor. I'm doing well, thank you. I'm here for {visit_type.lower()}.
"""
    
    if "Patient concerns" in focus_areas:
        base_content += "\nPatient: I have some concerns about the procedure..."
    
    if "Side effects" in focus_areas:
        base_content += "\nDr. Smith: Let's discuss the potential side effects..."
    
    if "Cost discussion" in focus_areas:
        base_content += "\nPatient: What about the cost of this treatment?"
    
    base_content += f"\n\n[This is a mock transcript generated with complexity level {complexity}]"
    
    return base_content

def generate_mock_prompt_result(prompt_title: str, transcript_name: str) -> str:
    """Generate mock prompt execution result"""
    return f"""Analysis Result for: {prompt_title}
Transcript: {transcript_name}
Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Based on the analysis of the provided transcript, here are the key findings:

• Patient exhibited typical concerns for this type of consultation
• Treatment plan was clearly communicated
• No significant risk factors identified
• Follow-up care instructions were provided

This is a mock result generated for demonstration purposes.
In a real implementation, this would be the output from an AI model analyzing the actual transcript content.
"""

def generate_mock_analysis_results(query: str, transcript_names: List[str]) -> Dict[str, Any]:
    """Generate mock analysis results"""
    individual_results = []
    for transcript in transcript_names:
        individual_results.append(f"""Results for {transcript}:
- Query: "{query}"
- Found 3 relevant mentions
- Key themes: consultation, patient care, treatment options
- Confidence score: 85%

This is a mock analysis result for demonstration purposes.""")
    
    summary = f"""Summary Analysis for query: "{query}"
Analyzed {len(transcript_names)} transcripts.

Key findings across all transcripts:
• Common theme 1: Patient consultation patterns
• Common theme 2: Treatment discussions
• Common theme 3: Follow-up care recommendations

Total mentions found: {len(transcript_names) * 3}
Average confidence: 85%
"""
    
    return {
        "individual_results": individual_results,
        "summary": summary,
        "metadata": {
            "query": query,
            "transcript_count": len(transcript_names),
            "analysis_date": datetime.now().isoformat()
        }
    }

def extract_text_from_file(uploaded_file) -> str:
    """Extract text content from uploaded file"""
    try:
        if uploaded_file.type == "text/plain":
            return str(uploaded_file.read(), "utf-8")
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # For demo purposes, return mock content
            return f"Mock content extracted from Word document: {uploaded_file.name}"
        elif uploaded_file.type == "application/pdf":
            # For demo purposes, return mock content
            return f"Mock content extracted from PDF document: {uploaded_file.name}"
        else:
            return "Unsupported file format"
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def export_analysis_results(analysis: Dict, format_type: str):
    """Export analysis results in specified format"""
    if format_type == "JSON":
        st.download_button(
            "Download JSON",
            json.dumps(analysis, indent=2, default=str),
            file_name=f"analysis_results_{analysis['id']}.json",
            mime="application/json"
        )
    elif format_type == "CSV":
        # Create CSV content
        csv_content = f"Query,Result_Count,Analysis_Date\n{analysis['query']},{analysis['result_count']},{analysis['created_at']}"
        st.download_button(
            "Download CSV",
            csv_content,
            file_name=f"analysis_results_{analysis['id']}.csv",
            mime="text/csv"
        )
    else:  # Excel
        st.info("Excel export would be implemented with openpyxl in production")

# Main application logic
def main():
    if not st.session_state.logged_in:
        show_auth()
    else:
        # Route to appropriate view based on project_view state
        view = st.session_state.project_view
        
        if view == 'menu':
            show_project_menu()
        elif view == 'transcript_generator':
            show_transcript_generator()
        elif view == 'prompt_tester':
            show_prompt_tester()
        elif view == 'transcript_analyzer':
            show_transcript_analyzer()
        else:
            # Default back to menu
            st.session_state.project_view = 'menu'
            show_project_menu()

if __name__ == "__main__":
    main()