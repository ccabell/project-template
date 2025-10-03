import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import uuid
import json

# Page configuration
st.set_page_config(
    page_title="A360 Project Hub",
    page_icon="🏢",
    layout="wide"
)

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    return create_client(
        "https://mepuegljvlnlonttanbb.supabase.co",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE"
    )

supabase = init_supabase()

# Initialize session state for simple storage
if 'projects' not in st.session_state:
    st.session_state.projects = []
if 'prompts' not in st.session_state:
    st.session_state.prompts = []
if 'user_logged_in' not in st.session_state:
    st.session_state.user_logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = "demo@a360.com"

# Simple auth bypass for testing
if not st.session_state.user_logged_in:
    st.title("🏢 A360 Internal Project Hub")
    st.markdown("### Quick Demo Access")
    
    if st.button("Continue as Demo User", type="primary"):
        st.session_state.user_logged_in = True
        st.rerun()
    
    st.info("Click above to access the demo. Full authentication coming soon.")
    st.stop()

# Main app
st.title("🏢 A360 Internal Project Hub")
st.markdown(f"Welcome back, **{st.session_state.current_user}**")

# Sidebar navigation
with st.sidebar:
    st.header("Navigation")
    page = st.selectbox("Go to:", ["Dashboard", "Projects", "Quick Prompt Test", "Settings"])
    
    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Dashboard
if page == "Dashboard":
    st.header("📊 Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Active Projects", len([p for p in st.session_state.projects if p.get('status') == 'active']))
    
    with col2:
        st.metric("Total Prompts", len(st.session_state.prompts))
    
    with col3:
        today_prompts = len([p for p in st.session_state.prompts if p.get('created_at', '').startswith(datetime.now().strftime('%Y-%m-%d'))])
        st.metric("Today's Prompts", today_prompts)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Recent Projects")
        if st.session_state.projects:
            for project in st.session_state.projects[-3:]:
                st.write(f"**{project['name']}** - {project.get('status', 'active')}")
        else:
            st.info("No projects yet. Create one in the Projects tab!")
    
    with col2:
        st.subheader("Recent Prompts")
        if st.session_state.prompts:
            for prompt in st.session_state.prompts[-3:]:
                st.write(f"**{prompt['prompt'][:50]}...** - {prompt.get('status', 'submitted')}")
        else:
            st.info("No prompts yet. Try the Quick Prompt Test!")

# Projects
elif page == "Projects":
    st.header("📁 Projects")
    
    tab1, tab2 = st.tabs(["My Projects", "Create New"])
    
    with tab1:
        if st.session_state.projects:
            for i, project in enumerate(st.session_state.projects):
                with st.expander(f"{project['name']} ({project.get('status', 'active')})"):
                    st.write(f"**Description:** {project.get('description', 'No description')}")
                    st.write(f"**Type:** {project.get('project_type', 'general')}")
                    st.write(f"**Priority:** {project.get('priority', 'medium')}")
                    st.write(f"**Created:** {project.get('created_at', 'Unknown')}")
                    
                    if st.button(f"Delete Project", key=f"del_{i}"):
                        st.session_state.projects.pop(i)
                        st.rerun()
        else:
            st.info("No projects found. Create your first project below!")
    
    with tab2:
        st.subheader("Create New Project")
        
        with st.form("new_project"):
            name = st.text_input("Project Name*")
            description = st.text_area("Description")
            project_type = st.selectbox("Type", ["general", "prompt_testing", "data_analysis", "web_development", "ai_research"])
            priority = st.selectbox("Priority", ["low", "medium", "high", "urgent"])
            
            if st.form_submit_button("Create Project", type="primary"):
                if name:
                    new_project = {
                        'id': str(uuid.uuid4()),
                        'name': name,
                        'description': description,
                        'project_type': project_type,
                        'priority': priority,
                        'status': 'active',
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'owner': st.session_state.current_user
                    }
                    st.session_state.projects.append(new_project)
                    
                    # Try to save to Supabase (if tables exist)
                    try:
                        supabase.table("projects").insert({
                            'name': name,
                            'description': description,
                            'project_type': project_type,
                            'priority': priority,
                            'status': 'active',
                            'owner_id': st.session_state.current_user,
                            'created_by': st.session_state.current_user
                        }).execute()
                        st.success(f"✅ Project '{name}' created and saved to database!")
                    except:
                        st.success(f"✅ Project '{name}' created locally!")
                    
                    st.rerun()
                else:
                    st.error("Please enter a project name")

# Quick Prompt Test
elif page == "Quick Prompt Test":
    st.header("🧪 Quick Prompt Tester")
    
    # Project selection
    if st.session_state.projects:
        project_names = ["No specific project"] + [p['name'] for p in st.session_state.projects]
        selected_project = st.selectbox("Select Project (optional)", project_names)
    else:
        selected_project = "No specific project"
        st.info("💡 Create a project first to organize your prompts!")
    
    # Prompt input
    prompt_text = st.text_area("Enter your prompt:", height=150, placeholder="Type your prompt here...")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.button("Submit Prompt", type="primary", disabled=not prompt_text.strip()):
            if prompt_text.strip():
                # Create prompt record
                new_prompt = {
                    'id': str(uuid.uuid4()),
                    'prompt': prompt_text,
                    'project': selected_project if selected_project != "No specific project" else None,
                    'status': 'submitted',
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'user_id': st.session_state.current_user
                }
                
                st.session_state.prompts.append(new_prompt)
                
                # Try to save to Supabase
                try:
                    project_id = None
                    if selected_project != "No specific project":
                        # Find project ID
                        for p in st.session_state.projects:
                            if p['name'] == selected_project:
                                project_id = p['id']
                                break
                    
                    supabase.table("prompts").insert({
                        'prompt': prompt_text,
                        'project_id': project_id,
                        'user_id': st.session_state.current_user,
                        'status': 'submitted'
                    }).execute()
                    st.success("✅ Prompt saved to database!")
                except:
                    st.success("✅ Prompt saved locally!")
                
                # Mock AI response
                st.subheader("📋 Mock AI Response")
                mock_response = f"""
**Analysis Complete!**

**Prompt**: {prompt_text[:100]}...

**Mock Response**: This is a simulated AI response. Your prompt has been analyzed and processed successfully.

**Key insights**:
- Word count: {len(prompt_text.split())} words
- Character count: {len(prompt_text)} characters
- Project: {selected_project}
- Status: Completed

*Note: This is a demo response. Real AI integration coming soon!*
                """
                st.markdown(mock_response)
                
                # Update prompt with response
                new_prompt['response'] = mock_response.strip()
                new_prompt['status'] = 'completed'
    
    # Show recent prompts
    st.divider()
    st.subheader("Your Recent Prompts")
    
    if st.session_state.prompts:
        for prompt in reversed(st.session_state.prompts[-10:]):  # Show last 10
            with st.expander(f"Prompt from {prompt['created_at']} - {prompt.get('status', 'submitted').upper()}"):
                st.markdown(f"**Prompt:** {prompt['prompt']}")
                if prompt.get('project'):
                    st.markdown(f"**Project:** {prompt['project']}")
                if prompt.get('response'):
                    st.markdown(f"**Response:** {prompt['response'][:200]}...")
                st.markdown(f"**Status:** {prompt.get('status', 'submitted')}")
    else:
        st.info("No prompts yet. Submit your first prompt above!")

# Settings
elif page == "Settings":
    st.header("⚙️ Settings")
    
    st.subheader("System Status")
    
    # Test Supabase connection
    try:
        # Try to ping Supabase
        result = supabase.auth.get_user()
        st.success("🟢 Supabase Connection: Active")
    except:
        st.warning("🟡 Supabase Connection: Limited (API working, auth not configured)")
    
    # Check table access
    try:
        supabase.table("projects").select("*").limit(1).execute()
        st.success("🟢 Projects Table: Accessible")
    except:
        st.warning("🟡 Projects Table: Not accessible (using local storage)")
    
    try:
        supabase.table("prompts").select("*").limit(1).execute()
        st.success("🟢 Prompts Table: Accessible")
    except:
        st.warning("🟡 Prompts Table: Not accessible (using local storage)")
    
    st.divider()
    
    st.subheader("Session Data")
    st.json({
        "Current User": st.session_state.current_user,
        "Projects Count": len(st.session_state.projects),
        "Prompts Count": len(st.session_state.prompts),
        "Session Active": st.session_state.user_logged_in
    })
    
    if st.button("Clear All Data", type="secondary"):
        st.session_state.projects = []
        st.session_state.prompts = []
        st.success("All data cleared!")
        st.rerun()

# Footer
st.divider()
st.markdown("*A360 Internal Project Hub - Demo Version*")
st.markdown("🔗 **Connected to Supabase** | 💾 **Local Storage Active** | 🧪 **Demo Mode**")