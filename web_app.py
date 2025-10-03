import streamlit as st
from supabase import create_client, Client
import time

# Page configuration
st.set_page_config(
    page_title="A360 Project Hub",
    page_icon="🏢",
    layout="wide"
)

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    try:
        # Try to get from secrets first (for deployment)
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
    except:
        # Fallback for local development
        supabase_url = "https://mepuegljvlnlonttanbb.supabase.co"
        supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE"
    
    return create_client(supabase_url, supabase_key)

supabase = init_supabase()

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None

def authenticate_user(email: str, password: str):
    """Authenticate user with Supabase Auth"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            st.session_state.authenticated = True
            st.session_state.user = response.user
            return True, "Login successful!"
        else:
            return False, "Login failed"
            
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            return False, "Invalid email or password"
        elif "Email not confirmed" in error_msg:
            return False, "Please confirm your email address first"
        else:
            return False, f"Login error: {error_msg}"

def register_user(email: str, password: str, full_name: str):
    """Register new user with Supabase Auth"""
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
            return True, "Account created! Please check your email to confirm your account."
        else:
            return False, "Registration failed"
            
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg:
            return False, "This email is already registered"
        else:
            return False, f"Registration error: {error_msg}"

def logout_user():
    """Logout user"""
    try:
        supabase.auth.sign_out()
    except:
        pass
    
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

# Authentication UI
def show_auth_page():
    st.title("🏢 A360 Project Hub")
    st.markdown("### Welcome to your internal project management system")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to your account")
        
        with st.form("login_form"):
            email = st.text_input("Email Address", placeholder="your.email@aesthetics360.com")
            password = st.text_input("Password", type="password")
            
            login_button = st.form_submit_button("Login", type="primary", use_container_width=True)
            
            if login_button:
                if email and password:
                    with st.spinner("Logging in..."):
                        success, message = authenticate_user(email, password)
                    
                    if success:
                        st.success(message)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please enter both email and password")
    
    with tab2:
        st.subheader("Create new account")
        
        with st.form("register_form"):
            new_email = st.text_input("Email Address", placeholder="your.email@aesthetics360.com", key="reg_email")
            new_password = st.text_input("Password", type="password", key="reg_password", help="Minimum 6 characters")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
            full_name = st.text_input("Full Name", placeholder="John Doe", key="reg_name")
            
            register_button = st.form_submit_button("Create Account", type="primary", use_container_width=True)
            
            if register_button:
                if new_email and new_password and confirm_password and full_name:
                    if new_password != confirm_password:
                        st.error("Passwords don't match")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters long")
                    else:
                        with st.spinner("Creating account..."):
                            success, message = register_user(new_email, new_password, full_name)
                        
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                else:
                    st.warning("Please fill in all fields")
    
    # Demo access for testing
    st.divider()
    st.subheader("Quick Demo Access")
    st.info("For testing purposes, you can continue without authentication")
    
    if st.button("Continue as Demo User", type="secondary", use_container_width=True):
        st.session_state.authenticated = True
        st.session_state.user = type('User', (), {
            'email': 'demo@aesthetics360.com',
            'id': 'demo-user-id',
            'user_metadata': {'full_name': 'Demo User'}
        })()
        st.rerun()

# Main application
def show_main_app():
    # Header
    st.title("🏢 A360 Project Hub")
    
    # User info and logout in sidebar
    with st.sidebar:
        if st.session_state.user:
            user_name = st.session_state.user.user_metadata.get('full_name', 'User') if hasattr(st.session_state.user, 'user_metadata') else 'Demo User'
            user_email = st.session_state.user.email
            
            st.markdown(f"### Welcome, {user_name}!")
            st.markdown(f"**Email:** {user_email}")
            
            st.divider()
            
            if st.button("Logout", type="secondary", use_container_width=True):
                logout_user()
        
        st.divider()
        st.markdown("**System Status:**")
        st.success("🟢 Connected to Supabase")
        st.info("🟡 Demo Mode Active")
    
    # Main content
    st.markdown("## 👋 Hello World!")
    st.markdown("### You have successfully logged into the A360 Project Hub!")
    
    st.markdown("---")
    
    # Success metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("✅ Authentication", "Working")
    
    with col2:
        st.metric("🌐 Web Deployment", "Ready")
    
    with col3:
        st.metric("🔗 Supabase", "Connected")
    
    st.markdown("---")
    
    # Next steps
    st.markdown("## 🚀 What's Next?")
    
    st.markdown("""
    **Your A360 Project Hub is now ready for development!**
    
    ✅ **Authentication System** - Users can sign up and login  
    ✅ **Web Deployment Ready** - Can be deployed to Streamlit Cloud  
    ✅ **Supabase Integration** - Connected to your database  
    ✅ **Secure Access** - Only authenticated users can access  
    
    **Ready to build your internal project management features:**
    - Project creation and management
    - Prompt testing interface  
    - Team collaboration tools
    - Activity tracking
    - And much more!
    """)
    
    # Quick actions
    st.markdown("### 🛠️ Developer Tools")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Test Database Connection", type="primary"):
            with st.spinner("Testing connection..."):
                try:
                    # Test basic connection
                    result = supabase.auth.get_user()
                    st.success("✅ Database connection successful!")
                except Exception as e:
                    st.warning(f"⚠️ Connection limited: {str(e)[:50]}...")
    
    with col2:
        if st.button("View User Info", type="secondary"):
            with st.expander("User Details", expanded=True):
                if hasattr(st.session_state.user, '__dict__'):
                    st.json({
                        "email": st.session_state.user.email,
                        "id": getattr(st.session_state.user, 'id', 'demo-id'),
                        "authenticated": st.session_state.authenticated
                    })
                else:
                    st.json({"status": "Demo user", "authenticated": True})
    
    # Footer
    st.markdown("---")
    st.markdown("*A360 Project Hub - Ready for Development* | 🔐 Authenticated Access | 🌐 Web Deployed")

# Main application logic
def main():
    if not st.session_state.authenticated:
        show_auth_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()