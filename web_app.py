# -*- coding: utf-8 -*-
import streamlit as st
from datetime import datetime
import json

# Page configuration
st.set_page_config(
    page_title="A360 Internal Project Hub",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
    
# Authentication functions
def login_user(email, password):
    # Demo login - works with any email/password
    if email and password:
        st.session_state.logged_in = True
        st.session_state.user_email = email
        return True, "Login successful!"
    return False, "Please enter email and password"

def logout_user():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Authentication UI
def show_auth():
    st.title(" A360 Internal Project Hub")
    st.markdown("### Welcome to your internal project management system")
    
    st.info(" **DEMO MODE** - Enter any email and password to explore the system!")
    
    tab1, tab2 = st.tabs(["Login", "Quick Demo"])
    
    with tab1:
        st.subheader("Login to your account")
        email = st.text_input("Email", placeholder="Enter any email", key="login_email")
        password = st.text_input("Password", type="password", placeholder="Enter any password", key="login_password")
        
        if st.button("Login", type="primary", key="login_btn"):
            success, message = login_user(email, password)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)
    
    with tab2:
        st.subheader("Quick Demo Access")
        st.markdown("Explore the A360 Project Hub with all three main projects:")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(" **Project 1**\nTranscript Generator")
        with col2:
            st.markdown(" **Project 2**\nPrompt Testing Tool")
        with col3:
            st.markdown(" **Project 3**\nTranscript Analysis")
        
        if st.button("Enter Demo Mode", type="primary", key="demo_btn"):
            st.session_state.logged_in = True
            st.session_state.user_email = "demo@a360.com"
            st.success(" Welcome to A360 Project Hub Demo!")
            st.rerun()

# Main application UI
def show_main_app():
    # Sidebar with user info and navigation
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.user_email}!")
        
        if st.button("Logout", key="logout_btn"):
            logout_user()
        
        st.divider()
        
        # Navigation
        page = st.selectbox(
            "Navigate to:",
            ["Dashboard", "Projects", "Quick Prompt Test", "System Info"],
            key="navigation"
        )
    
    # Main content based on selected page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Projects":
        show_projects()
    elif page == "Quick Prompt Test":
        show_prompt_tester()
    elif page == "System Info":
        show_system_info()

# Dashboard page
def show_dashboard():
    st.title(" A360 Project Hub Dashboard")
    
    st.success(" Welcome to the A360 Internal Project Hub! This is a fully functional demo of all three main projects.")
    
    # Display demo metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Available Projects", "3", "Ready")
    
    with col2:
        st.metric("Demo Prompts", "25", "Sample")
    
    with col3:
        st.metric("System Status", "100%", "Online")
    
    with col4:
        st.metric("Demo Features", "All", "Active")
    
    st.divider()
    
    # Project overview
    with col1:
        st.subheader("Available Projects")
        projects = [
            {"name": "Synthetic Transcript Generator", "type": "transcript_generator", "status": "Ready"},
            {"name": "Prompt Testing Sandbox", "type": "prompt_tester", "status": "Ready"},
            {"name": "Transcript Analysis Dashboard", "type": "transcript_analyzer", "status": "Ready"}
        ]
        
        for i, project in enumerate(projects):
            with st.container():
                st.markdown(f"**{project['name']}**")
                st.caption(f"Type: {project['type']} | Status: {project['status']}")
                if st.button(f"Explore {project['name']}", key=f"explore_{i}"):
                    st.info(f" {project['name']} - Full interactive demo available in the Projects tab!")
    
    with col2:
        st.subheader("System Status")
        st.success(" User Interface - Fully Operational")
        st.success(" Authentication - Working")
        st.success(" Project Demos - All Active")
        st.info(" Database Integration - Ready for Setup")
        
        st.markdown("### Demo Features:")
        st.markdown(" Interactive transcript generation")
        st.markdown(" Prompt testing with sample data")
        st.markdown(" Analysis dashboard with examples")
        st.markdown(" Full user interface preview")

# Projects page - Interactive Demos
def show_projects():
    st.title(" A360 Project Hub - Three Main Projects")
    
    st.markdown("### Complete interactive demonstrations of all three projects:")
    
    # Project 1 Demo
    with st.expander(" Project 1: Synthetic Transcript Generator", expanded=True):
        show_transcript_generator_demo()
    
    # Project 2 Demo  
    with st.expander(" Project 2: Prompt Testing Sandbox"):
        show_prompt_tester_demo()
    
    # Project 3 Demo
    with st.expander(" Project 3: Transcript Analysis Dashboard"):
        show_analysis_demo()

def show_transcript_generator_demo():
    st.markdown("""
    **Purpose**: Generate realistic consultation transcripts for training
    
    **Features**: Specialty selection, visit types, complexity controls, metadata tracking
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        specialty = st.selectbox("Specialty", ["Medspa", "Explant", "Venous"], key="gen_specialty")
        visit_type = st.selectbox("Visit Type", ["Initial Consultation", "Follow-up", "Treatment"], key="gen_visit")
        patient_name = st.text_input("Patient Name (optional)", "Demo Patient", key="gen_patient")
    
    with col2:
        complexity = st.slider("Complexity Level", 1, 5, 3, key="gen_complexity")
        length = st.selectbox("Transcript Length", ["Short", "Medium", "Long"], key="gen_length")
        focus_areas = st.multiselect("Focus Areas", ["Patient concerns", "Side effects", "Cost discussion"], key="gen_focus")
    
    if st.button("Generate Demo Transcript", type="primary", key="gen_demo"):
        with st.spinner("Generating transcript..."):
            demo_transcript = f"""DEMO CONSULTATION TRANSCRIPT
Patient: {patient_name}
Specialty: {specialty}
Visit Type: {visit_type}
Date: {datetime.now().strftime('%Y-%m-%d')}
Complexity: {complexity}/5 | Length: {length}

Dr. Smith: Good morning, {patient_name}. How are you feeling today?

Patient: Good morning, Doctor. I'm here for my {visit_type.lower()} regarding {specialty} treatment.

Dr. Smith: Excellent. Let's discuss your treatment plan and address any concerns.

[Demo transcript content - In the full system, this would be a detailed, AI-generated consultation]

Focus Areas: {', '.join(focus_areas) if focus_areas else 'Standard consultation'}
Generation completed with {complexity}/5 complexity level.
"""
        
        st.success(" Demo transcript generated!")
        st.text_area("Generated Content", demo_transcript, height=250, key="gen_output")
        
        st.download_button(
            " Download Demo Transcript",
            demo_transcript,
            file_name=f"demo_{specialty}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            key="gen_download"
        )

def show_prompt_tester_demo():
    st.markdown("""
    **Purpose**: Test AI prompts against transcript data with full tracking
    
    **Features**: File upload, prompt library, variable substitution, results comparison
    """)
    
    # Sample prompts and transcripts
    sample_prompts = [
        "Summarize the key points from this consultation",
        "Identify any side effects or concerns mentioned", 
        "Extract the main patient questions and concerns",
        "Analyze the treatment plan and recommendations"
    ]
    
    sample_transcripts = ["Demo Medspa Transcript", "Demo Explant Consultation", "Demo Venous Treatment"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_prompt = st.selectbox("Select Prompt Template", sample_prompts, key="test_prompt")
        selected_transcript = st.selectbox("Select Demo Transcript", sample_transcripts, key="test_transcript")
    
    with col2:
        st.markdown("**Upload Options** (Demo)")
        uploaded_file = st.file_uploader("Upload transcript file", type=['txt', 'docx', 'pdf'], key="test_upload")
        if uploaded_file:
            st.info(f"File ready: {uploaded_file.name}")
    
    if st.button("Run Demo Test", type="primary", key="test_demo"):
        with st.spinner("Processing prompt test..."):
            demo_result = f"""PROMPT TEST RESULTS
Prompt: "{selected_prompt}"
Transcript: {selected_transcript}
Execution Time: 2.1 seconds | Model: Demo-GPT-4

ANALYSIS OUTPUT:
Based on the {selected_transcript}, here are the key findings:

 Patient demonstrated typical consultation behavior for this specialty
 Clear communication between provider and patient
 Treatment options thoroughly discussed
 Follow-up instructions provided
 No significant risk factors identified

PERFORMANCE METRICS:
 Processing Time: 2.1s
 Tokens Used: 245
 Confidence Score: 94%
 Analysis Depth: High

This demonstrates the prompt testing system's capabilities.
Full version includes real AI analysis and detailed performance tracking.
"""
        
        st.success(" Demo test completed!")
        st.text_area("Test Results", demo_result, height=300, key="test_output")

def show_analysis_demo():
    st.markdown("""
    **Purpose**: Analyze PHI-removed real transcripts with bulk query capabilities
    
    **Features**: Database management, search/filter, bulk analysis, export options
    """)
    
    # Demo analysis query
    query_examples = [
        "Find mentions of side effects across all transcripts",
        "Analyze patient satisfaction indicators", 
        "Extract cost-related discussions from consultations",
        "Identify common patient concerns by specialty"
    ]
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_query = st.selectbox("Analysis Query", query_examples, key="analysis_query")
        
        # Mock transcript database
        demo_transcripts = [
            "Medspa_Consultation_001.txt (Botox discussion)",
            "Explant_Followup_002.txt (Recovery progress)", 
            "Venous_Treatment_003.txt (Procedure planning)",
            "Medspa_Initial_004.txt (First consultation)"
        ]
        
        selected_transcripts = st.multiselect(
            "Select Transcripts", 
            demo_transcripts,
            default=demo_transcripts[:2],
            key="analysis_transcripts"
        )
    
    with col2:
        st.markdown("**Search & Filter Options**")
        specialty_filter = st.selectbox("Filter by Specialty", ["All", "Medspa", "Explant", "Venous"], key="analysis_specialty")
        date_range = st.date_input("Date Range (optional)", key="analysis_date")
        keywords = st.text_input("Keywords", placeholder="e.g., botox, side effects", key="analysis_keywords")
    
    if st.button("Run Demo Analysis", type="primary", key="analysis_demo") and selected_transcripts:
        with st.spinner("Analyzing selected transcripts..."):
            analysis_result = f"""BULK ANALYSIS RESULTS
Query: "{selected_query}"
Transcripts Analyzed: {len(selected_transcripts)}
Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY FINDINGS:
 Found {len(selected_transcripts) * 4} relevant mentions across selected files
 Common themes: patient care, treatment planning, consultation protocols
 Average confidence score: 91%
 Analysis completed in 3.2 seconds

INDIVIDUAL RESULTS:
"""
            
            for i, transcript in enumerate(selected_transcripts):
                analysis_result += f"\n{i+1}. {transcript}:\n    4 relevant matches found\n    Key themes extracted\n    High confidence analysis\n    Export ready"
            
            analysis_result += f"\n\nEXPORT OPTIONS:\n JSON: Full detailed results with metadata\n CSV: Summary table with key metrics\n Excel: Formatted report with charts\n\nThis demonstrates the bulk analysis capabilities of the system.\n"
        
        st.success(" Demo analysis completed!")
        st.text_area("Analysis Results", analysis_result, height=400, key="analysis_output")
        
        # Demo export buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Export JSON", key="export_json"):
                st.info("JSON export ready for download")
        with col2:
            if st.button("Export CSV", key="export_csv"):
                st.info("CSV export ready for download")
        with col3:
            if st.button("Export Excel", key="export_excel"):
                st.info("Excel export ready for download")

# Quick Prompt Tester
def show_prompt_tester():
    st.title(" Quick Prompt Tester")
    
    st.info(" This is the simple prompt tester. For full prompt testing features, check out Project 2 in the Projects tab!")
    
    prompt = st.text_area("Enter your prompt for testing", height=150, placeholder="e.g., Analyze the key themes in this medical consultation...")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.button("Test Prompt", type="primary"):
            if prompt.strip():
                with st.spinner("Processing prompt..."):
                    # Demo processing
                    demo_response = f"""PROMPT TEST RESULT
Prompt: "{prompt[:100]}{'...' if len(prompt) > 100 else ''}"
Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DEMO ANALYSIS:
This prompt would be processed by the AI system and return:
 Structured analysis based on prompt requirements
 Relevant data extraction
 Key insights and patterns
 Confidence scores and metadata

In the full system, this connects to real AI models for processing.
For complete prompt testing features, use Project 2 in the Projects tab.
"""
                
                st.success(" Prompt processed!")
                st.text_area("Response", demo_response, height=200)
            else:
                st.warning("Please enter a prompt to test")
    
    with col2:
        st.markdown("**Quick Tips:**")
        st.markdown(" Be specific in your prompt")
        st.markdown(" Include context when needed")
        st.markdown(" Test different variations")
        st.markdown(" Use the Projects tab for advanced features")

# System Information
def show_system_info():
    st.title(" A360 Project Hub - System Information")
    
    st.success(" You are using the fully functional demo version of the A360 Internal Project Hub!")
    
    # System status
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("System Status")
        st.success(" User Interface - Fully Operational")
        st.success(" Authentication System - Working")
        st.success(" All Project Demos - Active")
        st.success(" Navigation & Controls - Functional")
        st.info(" Database Integration - Ready for Setup")
        st.info(" AI Integration - Ready for Connection")
    
    with col2:
        st.subheader("Available Features")
        st.markdown("  Project 1: Synthetic Transcript Generator")
        st.markdown("  Project 2: Prompt Testing Sandbox")
        st.markdown("  Project 3: Transcript Analysis Dashboard")
        st.markdown("  Interactive Dashboard")
        st.markdown("  Demo Authentication")
        st.markdown("  File Upload/Download")
    
    st.divider()
    
    # Technical details
    st.subheader("Technical Architecture")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Frontend**")
        st.markdown(" Streamlit Framework")
        st.markdown(" A360 Custom Theme")
        st.markdown(" Responsive Design")
        st.markdown(" Interactive Components")
    
    with col2:
        st.markdown("**Backend (Ready)**")
        st.markdown(" Supabase Database")
        st.markdown(" PostgreSQL Storage")
        st.markdown(" Row Level Security")
        st.markdown(" Real-time Updates")
    
    with col3:
        st.markdown("**Integration (Ready)**")
        st.markdown(" Warp AI Workflows")
        st.markdown(" N8N Automation")
        st.markdown(" File Processing")
        st.markdown(" Export Capabilities")
    
    st.divider()
    
    # Next steps
    st.subheader(" Next Steps for Full Deployment")
    
    with st.expander("1. Complete Database Setup", expanded=True):
        st.markdown("""
        **Required Actions:**
        - Run SQL schema in Supabase dashboard
        - Create initial admin user
        - Set up Row Level Security policies
        - Test database connections
        
        **Status**: SQL schema provided, ready for execution
        """)
    
    with st.expander("2. AI Integration"):
        st.markdown("""
        **Integration Points:**
        - Connect Warp AI workflows for transcript generation
        - Set up prompt processing pipelines
        - Configure analysis models
        - Test AI response handling
        
        **Status**: Application ready, integration hooks prepared
        """)
    
    with st.expander("3. User Management"):
        st.markdown("""
        **User System:**
        - Set up role-based access (Admin/Internal/External)
        - Configure project sharing permissions
        - Test access control flows
        - Create user onboarding process
        
        **Status**: Role system designed, ready for activation
        """)
    
    st.divider()
    
    # Current session info
    st.subheader("Current Session")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**User:** {st.session_state.user_email}")
        st.markdown(f"**Session Type:** Demo Mode")
        st.markdown(f"**Access Level:** Full Demo Access")
    
    with col2:
        st.markdown(f"**Login Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.markdown(f"**System Version:** v1.0 Demo")
        st.markdown(f"**Status:** All Systems Operational")

# Main application logic
def main():
    if not st.session_state.logged_in:
        show_auth()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
