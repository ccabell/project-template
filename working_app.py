import streamlit as st
import json
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="A360 Internal Project Hub",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

def show_auth():
    st.title("🏢 A360 Internal Project Hub")
    st.markdown("### Welcome to your internal project management system")
    
    tab1, tab2 = st.tabs(["Login", "Demo Access"])
    
    with tab1:
        st.subheader("Login to your account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary", key="login_btn"):
            if email and password:
                # Simple demo login - you can replace this with real authentication later
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.success("Login successful!")
                st.rerun()
            else:
                st.warning("Please enter both email and password")
    
    with tab2:
        st.subheader("Demo Access")
        st.info("👆 Use the Demo Access to explore the system without setting up the database")
        
        if st.button("Enter Demo Mode", type="primary"):
            st.session_state.logged_in = True
            st.session_state.user_email = "demo@a360.com"
            st.success("Welcome to demo mode!")
            st.rerun()

def show_main_app():
    # Sidebar with user info and navigation
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.user_email}!")
        
        if st.button("Logout", key="logout_btn"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.divider()
        
        # Navigation
        page = st.selectbox(
            "Navigate to:",
            ["Dashboard", "Projects", "Quick Prompt Test", "Demo Info"],
            key="navigation"
        )
    
    # Main content based on selected page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Projects":
        show_projects()
    elif page == "Quick Prompt Test":
        show_prompt_tester()
    elif page == "Demo Info":
        show_demo_info()

def show_dashboard():
    st.title("📊 Dashboard")
    
    st.info("🚧 This is a demo version. The full system is being set up with database integration.")
    
    # Display demo metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Projects", "3", "Demo")
    
    with col2:
        st.metric("Prompts", "12", "Sample")
    
    with col3:
        st.metric("Active", "3", "Ready")
    
    with col4:
        st.metric("This Week", "5", "Tests")
    
    st.divider()
    
    # Recent activity demo
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Available Projects")
        projects = [
            {"name": "Synthetic Transcript Generator", "type": "transcript_generator", "status": "Ready"},
            {"name": "Prompt Testing Sandbox", "type": "prompt_tester", "status": "Ready"},
            {"name": "Transcript Analysis Dashboard", "type": "transcript_analyzer", "status": "Ready"}
        ]
        
        for project in projects:
            with st.container():
                st.markdown(f"**{project['name']}**")
                st.caption(f"Type: {project['type']} | Status: {project['status']}")
                if st.button(f"Learn More about {project['name']}", key=f"learn_{project['name']}"):
                    st.info(f"This is the {project['name']} project. Full functionality coming soon!")
    
    with col2:
        st.subheader("System Status")
        st.success("✅ Authentication System - Working")
        st.success("✅ User Interface - Working") 
        st.warning("⚠️ Database Integration - In Progress")
        st.info("ℹ️ Project Interfaces - Ready for Testing")
        
        st.markdown("### Next Steps:")
        st.markdown("1. Complete database setup in Supabase")
        st.markdown("2. Test all three project interfaces")
        st.markdown("3. Configure user roles and permissions")

def show_projects():
    st.title("📁 Projects")
    
    st.markdown("## Three Main Projects")
    
    # Project 1
    with st.expander("🎯 Project 1: Synthetic Transcript Generator", expanded=True):
        st.markdown("""
        **Purpose**: Generate realistic consultation transcripts for training
        
        **Features**:
        - Specialty selection (Medspa, Explant, Venous)
        - Visit type options (Initial, Follow-up, Treatment, Post-Treatment)
        - Complexity and focus area controls
        - Patient metadata tracking
        - Export capabilities
        
        **Integration**: Ready for Warp AI/N8N workflows
        """)
        
        if st.button("Demo Project 1 Interface", key="demo_p1"):
            show_transcript_generator_demo()
    
    # Project 2  
    with st.expander("🧪 Project 2: Prompt Testing Tool"):
        st.markdown("""
        **Purpose**: Test AI prompts against transcript data
        
        **Features**:
        - File upload (TXT, DOCX, PDF)
        - Prompt library with variables
        - Test execution and tracking
        - Results comparison dashboard
        - Performance metrics
        
        **Status**: Interface complete, ready for AI integration
        """)
        
        if st.button("Demo Project 2 Interface", key="demo_p2"):
            show_prompt_tester_demo()
    
    # Project 3
    with st.expander("🔍 Project 3: Transcript Analysis Interface"):
        st.markdown("""
        **Purpose**: Analyze PHI-removed real transcripts
        
        **Features**:
        - Transcript database management
        - Search and filtering
        - Bulk analysis queries
        - Results export (CSV, Excel, JSON)
        - Keyword and specialty filtering
        
        **Status**: Ready for transcript uploads
        """)
        
        if st.button("Demo Project 3 Interface", key="demo_p3"):
            show_analysis_demo()

def show_transcript_generator_demo():
    st.subheader("🎯 Transcript Generator Demo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        specialty = st.selectbox("Specialty", ["Medspa", "Explant", "Venous"])
        visit_type = st.selectbox("Visit Type", ["Initial Consultation", "Follow-up", "Treatment"])
        patient_name = st.text_input("Patient Name (optional)", "Demo Patient")
    
    with col2:
        complexity = st.slider("Complexity", 1, 5, 3)
        length = st.selectbox("Length", ["Short", "Medium", "Long"])
        focus_areas = st.multiselect("Focus Areas", ["Patient concerns", "Side effects", "Cost"])
    
    if st.button("Generate Demo Transcript", type="primary"):
        with st.spinner("Generating transcript..."):
            # Demo transcript
            demo_transcript = f"""CONSULTATION TRANSCRIPT - DEMO
Patient: {patient_name}
Specialty: {specialty}
Visit Type: {visit_type}
Date: {datetime.now().strftime('%Y-%m-%d')}
Complexity Level: {complexity}

Dr. Smith: Good morning, {patient_name}. How are you feeling today?

Patient: Good morning, Doctor. I'm here for my {visit_type.lower()} regarding {specialty} treatment.

Dr. Smith: Excellent. Let's discuss your treatment options and address any concerns you might have.

[This is a demo transcript. The full system will generate realistic, detailed transcripts using AI.]

Focus Areas Included: {', '.join(focus_areas) if focus_areas else 'None selected'}
Length: {length}
"""
        
        st.success("✅ Demo transcript generated!")
        st.text_area("Generated Content", demo_transcript, height=300)
        
        st.download_button(
            "📄 Download Demo Transcript",
            demo_transcript,
            file_name=f"demo_transcript_{specialty}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )

def show_prompt_tester_demo():
    st.subheader("🧪 Prompt Testing Demo")
    
    # Sample prompts
    sample_prompts = [
        "Summarize the key points from this consultation",
        "Identify any side effects mentioned in the transcript", 
        "Extract patient concerns and questions",
        "Analyze the treatment plan discussed"
    ]
    
    selected_prompt = st.selectbox("Select Demo Prompt", sample_prompts)
    
    # Mock transcript selection
    sample_transcripts = ["Demo Medspa Transcript", "Demo Explant Consultation", "Demo Venous Treatment"]
    selected_transcript = st.selectbox("Select Demo Transcript", sample_transcripts)
    
    if st.button("Run Demo Test", type="primary"):
        with st.spinner("Processing..."):
            demo_result = f"""Demo Analysis Result
Prompt: "{selected_prompt}"
Transcript: {selected_transcript}
Execution Time: 2.3 seconds
Model: Demo-GPT-4

Analysis Result:
Based on the {selected_transcript}, here are the key findings:

• Patient showed typical concerns for this consultation type
• Treatment options were clearly explained
• Follow-up care instructions provided
• No major risk factors identified

This is a demonstration of how the prompt testing system will work.
In the full system, this would be real AI analysis of actual transcripts.

Performance Metrics:
- Tokens Used: 150
- Confidence: 92%
- Processing Time: 2.3s
"""
        
        st.success("✅ Demo analysis complete!")
        st.text_area("Analysis Result", demo_result, height=300)

def show_analysis_demo():
    st.subheader("🔍 Analysis Dashboard Demo")
    
    st.markdown("### Demo Analysis Query")
    
    query_examples = [
        "Find mentions of side effects across all transcripts",
        "Analyze patient satisfaction indicators", 
        "Extract cost-related discussions",
        "Identify common patient concerns"
    ]
    
    selected_query = st.selectbox("Demo Query", query_examples)
    
    # Mock transcript database
    st.markdown("### Available Demo Transcripts")
    demo_transcripts = [
        {"name": "Medspa_Consultation_001", "specialty": "Medspa", "keywords": ["botox", "consultation"]},
        {"name": "Explant_Followup_002", "specialty": "Explant", "keywords": ["removal", "recovery"]},
        {"name": "Venous_Treatment_003", "specialty": "Venous", "keywords": ["veins", "procedure"]}
    ]
    
    selected_transcripts = st.multiselect(
        "Select Transcripts for Analysis",
        [f"{t['name']} ({t['specialty']})" for t in demo_transcripts],
        default=[f"{demo_transcripts[0]['name']} ({demo_transcripts[0]['specialty']})"]
    )
    
    if st.button("Run Demo Analysis", type="primary") and selected_transcripts:
        with st.spinner("Analyzing transcripts..."):
            demo_analysis = f"""Analysis Results for: "{selected_query}"
Transcripts Analyzed: {len(selected_transcripts)}
Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Summary Findings:
• Found {len(selected_transcripts) * 3} relevant mentions across selected transcripts
• Common themes: consultation patterns, patient care, treatment planning
• Average confidence score: 87%

Individual Results:
"""
            
            for transcript in selected_transcripts:
                demo_analysis += f"\n{transcript}:\n- 3 relevant matches found\n- Key themes identified\n- High confidence analysis\n"
            
            demo_analysis += f"""
Export Options Available:
- JSON format with full details
- CSV summary with key metrics  
- Excel report with charts

This demonstrates the analysis capabilities of the full system.
"""
        
        st.success("✅ Demo analysis complete!")
        st.text_area("Analysis Results", demo_analysis, height=400)

def show_prompt_tester():
    st.title("🧪 Quick Prompt Tester")
    
    st.info("This is the original prompt tester. Use the Projects tab to see the full system demos.")
    
    prompt = st.text_area("Enter your prompt", height=150)
    
    if st.button("Submit Prompt", type="primary"):
        if prompt.strip():
            st.success("✅ Prompt submitted!")
            st.markdown("**Your prompt:**")
            st.write(prompt)
            st.info("In the full system, this would be processed by AI and saved to the database.")
        else:
            st.warning("Please enter a prompt")

def show_demo_info():
    st.title("ℹ️ Demo Information")
    
    st.markdown("""
    ## A360 Internal Project Hub - Demo Mode
    
    You are currently viewing a demonstration version of the complete system.
    
    ### What's Working:
    ✅ **User Interface** - Complete Streamlit interface  
    ✅ **Navigation** - All pages and sections accessible  
    ✅ **Project Demos** - Interactive demonstrations of all three projects  
    ✅ **Authentication Flow** - Login/logout functionality  
    
    ### What's Being Set Up:
    🚧 **Database Integration** - Supabase tables and relationships  
    🚧 **User Roles** - Admin, Internal, External access control  
    🚧 **Real Data Processing** - AI integration for transcripts and analysis  
    
    ### The Three Main Projects:
    
    1. **Synthetic Transcript Generator**
       - Generate realistic consultation transcripts
       - Multiple specialties and visit types
       - Configurable complexity and focus areas
    
    2. **Prompt Testing Sandbox**
       - Test AI prompts against transcript data
       - Upload files and manage prompt library
       - Compare results and track performance
    
    3. **Transcript Analysis Dashboard**
       - Analyze real PHI-removed transcripts
       - Bulk queries across multiple files
       - Export results in various formats
    
    ### Next Steps for Full Deployment:
    
    1. **Complete Database Setup**
       - Run the SQL commands in Supabase
       - Set up Row Level Security policies
       - Create initial admin user
    
    2. **AI Integration**
       - Connect Warp AI workflows
       - Configure prompt processing
       - Set up analysis pipelines
    
    3. **User Management**
       - Set up role-based access
       - Configure project sharing
       - Test access controls
    
    ### Technical Details:
    - **Frontend**: Streamlit with A360 branding
    - **Database**: Supabase with PostgreSQL
    - **Authentication**: Supabase Auth
    - **AI Integration**: Ready for Warp AI/N8N workflows
    """)
    
    if st.button("Test Database Connection"):
        st.info("Database connection test would run here. Currently in demo mode.")

# Main application logic
def main():
    if not st.session_state.logged_in:
        show_auth()
    else:
        show_main_app()

if __name__ == "__main__":
    main()