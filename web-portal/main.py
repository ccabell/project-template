import streamlit as st
from utils.supabase_client import supabase
import os
import time
from datetime import datetime

st.set_page_config(
    page_title="A360 Portal", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for B360 styling
st.markdown("""
<style>
    .main-header {
        color: #547BA3;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .project-card {
        background: #F9FAFB;
        border: 1px solid #EAECF0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .status-indicator {
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    .status-active {
        background: #ECFDF3;
        color: #17826A;
    }
    .status-pending {
        background: #FFFAEB;
        color: #F79009;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "user" not in st.session_state:
    st.session_state["user"] = None
if "selected_project" not in st.session_state:
    st.session_state["selected_project"] = None

# Authentication
if st.session_state["user"] is None:
    st.markdown('<h1 class="main-header">A360 – Consultation & Agent Testing</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Portal Access")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your.email@domain.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                try:
                    res = supabase.auth.sign_in_with_password({
                        "email": email, 
                        "password": password
                    })
                    if res.user:
                        st.session_state["user"] = res.user.email
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                except Exception as e:
                    st.error(f"❌ Authentication error: {str(e)}")
        
        with st.expander("ℹ️ Access Information"):
            st.markdown("""
            **A360 Portal Features:**
            - 📊 Project tracking and management
            - 🤖 Agent testing dashboard
            - 👥 User access management for external collaborators
            - 🔗 Integration with Warp projects
            - 📝 Real-time project status updates
            
            **Security:** This portal provides password-protected access to internal project management tools.
            """)

else:
    # Main application interface
    st.sidebar.success(f"👤 Logged in as {st.session_state['user']}")
    
    # Sidebar navigation
    st.sidebar.markdown("---")
    page = st.sidebar.selectbox(
        "📍 Navigate",
        ["🏠 Dashboard", "📊 Projects", "🧪 Prompt Testing", "🤖 Agent Testing", "👥 User Management", "⚙️ Settings"]
    )
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state["user"] = None
        st.session_state["selected_project"] = None
        st.rerun()
    
    # Main content area
    st.markdown('<h1 class="main-header">A360 Portal</h1>', unsafe_allow_html=True)
    
    if page == "🏠 Dashboard":
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Active Projects", "7", "2")
        with col2:
            st.metric("Test Users", "23", "5")
        with col3:
            st.metric("Agents Running", "4", "-1")
        with col4:
            st.metric("Success Rate", "94.2%", "2.1%")
        
        st.markdown("### 📈 Recent Activity")
        
        # Mock recent activity data
        activities = [
            {"time": "2 min ago", "action": "Project 'MariaDB Sync' updated", "user": "Chris", "status": "active"},
            {"time": "15 min ago", "action": "New test user created for 'N8N Interface'", "user": "System", "status": "active"},
            {"time": "1 hour ago", "action": "Agent test completed", "user": "TestBot", "status": "active"},
            {"time": "2 hours ago", "action": "PageCraft integration deployed", "user": "Chris", "status": "pending"},
        ]
        
        for activity in activities:
            status_class = f"status-{activity['status']}"
            st.markdown(f"""
            <div class="project-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{activity['action']}</strong><br>
                        <small>by {activity['user']}</small>
                    </div>
                    <div>
                        <span class="status-indicator {status_class}">{activity['status'].title()}</span><br>
                        <small>{activity['time']}</small>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    elif page == "📊 Projects":
        st.markdown("### 🔗 B360 Project Integration")
        
        # Integration with B360 projects
        b360_projects = [
            {"name": "MariaDB Sync Project", "status": "Active", "collaborators": 3, "last_updated": "2024-10-03"},
            {"name": "N8N Interface Project", "status": "Testing", "collaborators": 5, "last_updated": "2024-10-02"},
            {"name": "PageCraft Bliss Forge API", "status": "Active", "collaborators": 2, "last_updated": "2024-10-03"},
            {"name": "Firecrawl Project", "status": "Development", "collaborators": 1, "last_updated": "2024-10-01"},
            {"name": "Warp Work Tracker", "status": "Active", "collaborators": 4, "last_updated": "2024-10-03"},
        ]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            for project in b360_projects:
                status_class = "status-active" if project["status"] == "Active" else "status-pending"
                st.markdown(f"""
                <div class="project-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4>{project['name']}</h4>
                            <p>👥 {project['collaborators']} collaborators • 📅 Updated: {project['last_updated']}</p>
                        </div>
                        <span class="status-indicator {status_class}">{project['status']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Manage {project['name']}", key=f"manage_{project['name']}"):
                    st.session_state["selected_project"] = project['name']
        
        with col2:
            st.markdown("#### 🎯 Quick Actions")
            if st.button("➕ Create Test User", use_container_width=True):
                st.success("Test user creation form would open here")
            if st.button("🔗 Sync Projects", use_container_width=True):
                st.info("Syncing with B360 repositories...")
            if st.button("📊 Generate Report", use_container_width=True):
                st.success("Project report generated!")
        
        if st.session_state["selected_project"]:
            st.markdown(f"### 🔧 Managing: {st.session_state['selected_project']}")
            
            tab1, tab2, tab3 = st.tabs(["👥 Collaborators", "🔑 Access Control", "📋 Activity Log"])
            
            with tab1:
                st.markdown("**External Collaborators:**")
                st.text("• john.doe@external.com (Read/Write)")
                st.text("• jane.smith@partner.org (Read Only)")
                
                with st.form("add_collaborator"):
                    email = st.text_input("Add Collaborator Email")
                    access = st.selectbox("Access Level", ["Read Only", "Read/Write", "Admin"])
                    if st.form_submit_button("Add Collaborator"):
                        st.success(f"Added {email} with {access} access")
            
            with tab2:
                st.markdown("**Repository Access:**")
                st.checkbox("Production repository (core team only)", value=False, disabled=True)
                st.checkbox("Collaborator snapshots", value=True)
                st.checkbox("Documentation access", value=True)
                st.checkbox("API documentation", value=True)
                
            with tab3:
                st.text("2024-10-03 14:30 - Snapshot updated for external collaborators")
                st.text("2024-10-03 12:15 - New collaborator added: john.doe@external.com")
                st.text("2024-10-02 16:45 - Database schema updated")
    
    elif page == "🧪 Prompt Testing":
        st.markdown("### 🧪 Prompt Testing Laboratory")
        
        # Quick access to prompt testing features
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🎯 Single Prompt Test", use_container_width=True):
                st.info("🚀 Navigate to dedicated Prompt Testing page for full functionality")
        
        with col2:
            if st.button("📊 Batch Testing", use_container_width=True):
                st.info("🚀 Navigate to dedicated Prompt Testing page for full functionality")
        
        with col3:
            if st.button("⚖️ A/B Comparison", use_container_width=True):
                st.info("🚀 Navigate to dedicated Prompt Testing page for full functionality")
        
        with col4:
            if st.button("🏆 Benchmarking", use_container_width=True):
                st.info("🚀 Navigate to dedicated Prompt Testing page for full functionality")
        
        st.markdown("---")
        
        # Available agents/models for testing
        st.markdown("#### 🤖 Available Agents & Models")
        
        agent_categories = {
            "A360 Ecosystem": [
                "🤖 A360 GenAI Agent",
                "📦 DataSync Agent", 
                "🔍 ContentCrawl Agent",
                "📊 MariaDB Query Agent",
                "⚡ N8N Workflow Agent"
            ],
            "External APIs": [
                "🤖 OpenAI GPT-4",
                "🤖 Claude 3.5 Sonnet",
                "🤖 Custom Agent"
            ]
        }
        
        col1, col2 = st.columns(2)
        
        with col1:
            for category, agents in agent_categories.items():
                st.markdown(f"**{category}:**")
                for agent in agents:
                    st.text(f"  {agent}")
        
        with col2:
            st.markdown("#### 📊 Recent Test Statistics")
            
            col2a, col2b, col2c = st.columns(3)
            with col2a:
                st.metric("Tests Today", "47", "+12")
            with col2b:
                st.metric("Avg Response Time", "1.8s", "-0.2s")
            with col2c:
                st.metric("Success Rate", "96.2%", "+1.1%")
        
        # Quick test interface
        st.markdown("#### ⚡ Quick Test")
        
        with st.form("quick_test"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                quick_prompt = st.text_input("Enter a quick prompt to test:")
                quick_agent = st.selectbox("Agent:", ["A360 GenAI Agent", "OpenAI GPT-4", "Claude 3.5 Sonnet"])
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                submitted = st.form_submit_button("🚀 Test", use_container_width=True)
            
            if submitted and quick_prompt.strip():
                with st.spinner(f"Testing with {quick_agent}..."):
                    time.sleep(1.5)
                    st.success(f"✅ Test completed! Response: 'Sample response from {quick_agent} to: {quick_prompt[:50]}...'")
                    st.info("📊 View full results and advanced testing options in the dedicated Prompt Testing page")
    
    elif page == "🤖 Agent Testing":
        st.markdown("### 🧪 Agent Testing Dashboard")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🤖 Active Agents")
            agents = [
                {"name": "DataSync Agent", "status": "Running", "uptime": "2h 34m"},
                {"name": "ContentCrawl Agent", "status": "Running", "uptime": "1h 12m"},
                {"name": "TestValidation Agent", "status": "Stopped", "uptime": "0m"},
                {"name": "UserAccess Agent", "status": "Running", "uptime": "4h 56m"},
            ]
            
            for agent in agents:
                status_emoji = "🟢" if agent["status"] == "Running" else "🔴"
                st.text(f"{status_emoji} {agent['name']} - {agent['uptime']}")
        
        with col2:
            st.markdown("#### 📊 Test Results")
            st.success("✅ Database connection: PASS")
            st.success("✅ API endpoints: PASS")
            st.warning("⚠️ External auth: TESTING")
            st.success("✅ File operations: PASS")
        
        st.markdown("---")
        
        st.markdown("#### 🚀 Run New Test")
        test_type = st.selectbox("Test Type", ["API Integration", "Database Sync", "User Access", "Full System"])
        if st.button("Start Test"):
            st.info(f"Starting {test_type} test...")
    
    elif page == "👥 User Management":
        st.markdown("### 👥 User Access Management")
        
        st.markdown("#### 🔐 Test User Creation")
        st.markdown("Create temporary users for external collaborators to test specific projects.")
        
        with st.form("create_test_user"):
            col1, col2 = st.columns(2)
            with col1:
                test_email = st.text_input("Test User Email")
                project_access = st.multiselect(
                    "Project Access", 
                    ["MariaDB Sync", "N8N Interface", "PageCraft API", "Firecrawl", "Warp Tracker"]
                )
            with col2:
                access_duration = st.selectbox("Access Duration", ["1 day", "3 days", "1 week", "1 month"])
                permissions = st.selectbox("Permission Level", ["View Only", "Comment", "Collaborate"])
            
            if st.form_submit_button("Create Test User"):
                st.success(f"✅ Test user created: {test_email}")
                st.info(f"Access expires in {access_duration}")
        
        st.markdown("#### 👤 Active Test Users")
        test_users = [
            {"email": "reviewer@client.com", "projects": ["N8N Interface"], "expires": "2024-10-05", "status": "Active"},
            {"email": "dev@partner.org", "projects": ["PageCraft API", "Firecrawl"], "expires": "2024-10-10", "status": "Active"},
            {"email": "tester@external.com", "projects": ["MariaDB Sync"], "expires": "2024-10-04", "status": "Expiring"},
        ]
        
        for user in test_users:
            status_class = "status-active" if user["status"] == "Active" else "status-pending"
            projects_str = ", ".join(user["projects"])
            st.markdown(f"""
            <div class="project-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{user['email']}</strong><br>
                        <small>Projects: {projects_str}</small><br>
                        <small>Expires: {user['expires']}</small>
                    </div>
                    <span class="status-indicator {status_class}">{user['status']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    elif page == "⚙️ Settings":
        st.markdown("### ⚙️ Portal Configuration")
        
        tab1, tab2, tab3 = st.tabs(["🔗 Integrations", "🔒 Security", "📧 Notifications"])
        
        with tab1:
            st.markdown("#### 🔗 Warp Integration")
            st.checkbox("Enable Warp project sync", value=True)
            st.checkbox("Auto-update project status", value=True)
            
            st.markdown("#### 📊 Database Integration")
            st.text_input("Reference DB Host", value="pma.nextnlp.com", disabled=True)
            st.info("⚠️ Reference database is for development only")
            
            st.markdown("#### 🎨 PageCraft Integration")
            st.checkbox("Enable PageCraft publishing", value=True)
            st.text_input("PageCraft API URL", value="http://localhost:8080/api")
        
        with tab2:
            st.markdown("#### 🔒 Access Control")
            st.slider("Session timeout (minutes)", 30, 480, 120)
            st.checkbox("Require 2FA for admin functions", value=False)
            st.checkbox("Log all user activities", value=True)
        
        with tab3:
            st.markdown("#### 📧 Notification Settings")
            st.checkbox("Email on new collaborator added", value=True)
            st.checkbox("Email on project updates", value=True)
            st.checkbox("Email on test failures", value=True)

# Footer
st.markdown("---")
st.markdown(
    "**A360 Portal** | Powered by B360 Project Template | "
    f"Session: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)