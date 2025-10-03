# 🚀 A360 Internal Project Hub - Deployment Guide

## Overview
This guide will help you deploy your A360 Internal Project Hub to Streamlit Cloud and set up the complete system for ongoing use.

## 🗄️ Step 1: Set Up Supabase Database

1. **Go to your Supabase project**: https://mepuegljvlnlonttanbb.supabase.co
2. **Navigate to SQL Editor**
3. **Run the database schema** from `database_schema.sql` file (copy and paste the entire content)
4. **Verify tables are created**:
   - `profiles`
   - `projects` 
   - `prompts`
   - `activity_log`
   - `project_collaborators`
   - `app_settings`

## 🔐 Step 2: Configure Authentication

1. **In Supabase Dashboard**:
   - Go to **Authentication > Settings**
   - Enable **Email** provider
   - Set **Site URL**: `https://your-app-name.streamlit.app` (we'll get this in Step 4)
   - Add **Redirect URLs**: `https://your-app-name.streamlit.app`

2. **Email Templates** (optional):
   - Customize sign-up confirmation emails
   - Customize password reset emails

## 📁 Step 3: Prepare Your GitHub Repository

1. **Create a new GitHub repository**:
   ```bash
   # In your project directory
   git init
   git add .
   git commit -m \"Initial A360 Project Hub setup\"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/a360-project-hub.git
   git push -u origin main
   ```

2. **Repository Structure**:
   ```
   a360-project-hub/
   ├── app.py                    # Main application
   ├── requirements.txt          # Dependencies
   ├── database_schema.sql       # Database setup
   ├── .streamlit/
   │   ├── config.toml          # Streamlit configuration
   │   └── secrets.toml         # Local secrets (DO NOT COMMIT)
   ├── DEPLOYMENT_GUIDE.md      # This file
   └── README.md               # Project documentation
   ```

3. **Create .gitignore**:
   ```
   .streamlit/secrets.toml
   __pycache__/
   *.pyc
   .env
   .DS_Store
   ```

## ☁️ Step 4: Deploy to Streamlit Cloud

1. **Go to**: https://share.streamlit.io/

2. **Sign in** with your GitHub account

3. **Deploy new app**:
   - Repository: `YOUR_USERNAME/a360-project-hub`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: Choose your custom URL (e.g., `a360-project-hub`)

4. **Configure Secrets** in Streamlit Cloud:
   - Go to your app settings
   - Add the following secrets:
   ```toml
   [supabase]
   url = \"https://mepuegljvlnlonttanbb.supabase.co\"
   key = \"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE\"
   
   [app]
   title = \"A360 Internal Project Hub\"
   admin_email = \"ccabell@aesthetics360.com\"
   ```

5. **Update Supabase Auth Settings**:
   - Go back to Supabase Dashboard
   - Update **Site URL** and **Redirect URLs** with your actual Streamlit app URL

## 🎯 Step 5: Access Your Deployed Application

### Your App URLs
- **App URL**: `https://your-app-name.streamlit.app`
- **Admin Panel**: Use your deployed app with admin credentials

### Initial Setup
1. **Create your admin account**:
   - Go to your deployed app
   - Click \"Sign Up\"
   - Use email: `ccabell@aesthetics360.com`
   - Create a secure password
   - Confirm email through Supabase

2. **Set admin role** (via Supabase SQL Editor):
   ```sql
   UPDATE public.profiles 
   SET role = 'admin' 
   WHERE email = 'ccabell@aesthetics360.com';
   ```

## 🔄 Step 6: Future Updates

### To Update Your App:
1. **Make changes locally**
2. **Commit and push**:
   ```bash
   git add .
   git commit -m \"Your update message\"
   git push
   ```
3. **Streamlit Cloud will auto-deploy**

### To Access Your App:
- **URL**: `https://your-app-name.streamlit.app`
- **Login**: Use your registered email/password
- **Features**:
  - Dashboard with project overview
  - Project management
  - Quick prompt testing
  - Activity tracking

## 🛡️ Security & Access Management

### User Management:
1. **Add team members**:
   - They can sign up directly through your app
   - Set their roles via Supabase dashboard
   - Roles: `admin`, `manager`, `user`

2. **Access Control**:
   - Row Level Security (RLS) is enabled
   - Users only see their own projects and collaborations
   - Admins have broader access

### Backup Strategy:
1. **Database backups**: Automatic via Supabase
2. **Code backups**: GitHub repository
3. **Regular exports**: Use Supabase dashboard to export data

## 📞 Support & Maintenance

### Monitoring Your App:
1. **Streamlit Cloud Dashboard**: Monitor app health and usage
2. **Supabase Dashboard**: Monitor database performance
3. **GitHub**: Track code changes and issues

### Troubleshooting:
1. **App won't load**: Check Streamlit Cloud logs
2. **Database errors**: Check Supabase logs
3. **Auth issues**: Verify Supabase Auth configuration

### Updating Dependencies:
1. **Edit `requirements.txt`**
2. **Push to GitHub**
3. **Streamlit will auto-update**

## 🎨 Customization

### Branding:
- Update colors in `.streamlit/config.toml`
- Modify app title in `app.py`
- Add company logo (upload to GitHub repo)

### Features:
- Add new project types in database schema
- Create custom prompt templates
- Add file upload capabilities
- Integrate with external APIs

## 📋 Maintenance Checklist

### Weekly:
- [ ] Check app performance
- [ ] Review user activity
- [ ] Backup critical data

### Monthly:
- [ ] Update dependencies if needed
- [ ] Review user access and permissions
- [ ] Check Supabase usage limits

### Quarterly:
- [ ] Full data export
- [ ] Security review
- [ ] Feature enhancement planning

## 🚀 Going Live Checklist

- [ ] Database schema deployed
- [ ] Authentication configured
- [ ] GitHub repository set up
- [ ] Streamlit Cloud deployment complete
- [ ] Secrets configured
- [ ] Admin account created
- [ ] Initial testing completed
- [ ] Team members invited
- [ ] Documentation updated

## 📬 Your Deployed System

**Once deployed, you'll have:**

✅ **Web App**: `https://your-app-name.streamlit.app`
✅ **User Authentication**: Sign up/login system
✅ **Project Management**: Create and manage internal projects
✅ **Prompt Testing**: Quick AI prompt testing interface
✅ **Data Storage**: All data securely stored in Supabase
✅ **Team Collaboration**: Multi-user support with role-based access
✅ **Activity Tracking**: Monitor system usage and project progress

**This becomes your central hub for all internal A360 projects!**

---

🎉 **Congratulations!** Your A360 Internal Project Hub is now live and ready for your team to use.

For questions or support, contact: ccabell@aesthetics360.com