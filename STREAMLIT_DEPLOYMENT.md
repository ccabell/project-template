# 🚀 Streamlit Cloud Deployment Configuration

## ✅ **WORKING CONFIGURATION** (Do Not Change)

Your Streamlit Cloud app is currently configured as:

- **Repository**: `ccabell/project-template`
- **Branch**: `b360-main` 
- **Main File**: `web_app.py`
- **App URL**: https://ib8imbfngdgvpaj6xgnqup.streamlit.app/

## 📁 **File Structure**

To maintain compatibility, these files are kept in sync:

```
project-template/
├── app.py                 # Main development file
├── web_app.py            # DEPLOYMENT FILE (auto-synced from app.py)
├── streamlit_app.py      # Backup deployment file
└── main_app.py           # Advanced version with full database
```

## 🔄 **Deployment Workflow**

### Making Updates:

1. **Edit `app.py`** - this is your main development file
2. **Sync to deployment file**:
   ```bash
   cp app.py web_app.py
   git add web_app.py
   git commit -m "Update deployment file"
   git push origin b360-main
   ```
3. **Wait 30-60 seconds** for Streamlit Cloud to auto-deploy

### Quick Deploy Script:

```bash
# Copy this to deploy_app.bat for one-click deployment
@echo off
cp app.py web_app.py
git add web_app.py
git commit -m "Deploy updated app - %date% %time%"
git push origin b360-main
echo Deployment pushed! Check https://ib8imbfngdgvpaj6xgnqup.streamlit.app/ in 60 seconds
pause
```

## ⚠️ **CRITICAL: Never Change These Settings**

In Streamlit Cloud "Manage app" settings, keep:
- Branch: `b360-main` (do not change to main)
- Main file: `web_app.py` (do not change to app.py)
- Repository: `ccabell/project-template`

## 🛠️ **Troubleshooting**

### If the site shows old content:

1. **Check the deployment file is updated**:
   ```bash
   git status
   git log --oneline -5
   ```

2. **Force sync the deployment file**:
   ```bash
   cp app.py web_app.py
   git add web_app.py
   git commit -m "Force sync deployment file"
   git push origin b360-main
   ```

3. **In Streamlit Cloud**: Go to "Manage app" → "Reboot app"

### If you see "file not found" errors:

- Make sure you're on the `b360-main` branch
- Ensure `web_app.py` exists and is up to date
- Check that `requirements.txt` contains all dependencies

### If the site won't load at all:

1. Check Streamlit Cloud logs in "Manage app"
2. Look for Python errors or missing dependencies
3. Compare `web_app.py` with `app.py` to ensure they match

## 📦 **Dependencies**

Current `requirements.txt`:
```
streamlit
supabase
pandas
```

These are automatically installed by Streamlit Cloud.

## 🔐 **Secrets Management**

Streamlit Cloud uses secrets from `.streamlit/secrets.toml`:
```toml
[supabase]
url = "https://mepuegljvlnlonttanbb.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1lcHVlZ2xqdmxubG9udHRhbmJiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzODQzMTgsImV4cCI6MjA3NDk2MDMxOH0.TlhlF85jEcRvbObR7zpGr1d2OHBJwdEhx43_q9e8zeE"

[app]
title = "A360 Internal Project Hub"
admin_email = "ccabell@aesthetics360.com"
```

## 🎯 **Current App Features**

Your deployed app includes:

### 🚪 **Authentication**
- Demo mode (no login required)
- Any email/password works
- Session management

### 📊 **Dashboard** 
- System status overview
- Project metrics
- Quick access to all features

### 📁 **Three Main Projects**

1. **🎯 Synthetic Transcript Generator**
   - Specialty selection (Medspa/Explant/Venous)
   - Visit type options
   - Complexity controls
   - Download capabilities

2. **🧪 Prompt Testing Sandbox**
   - File upload simulation
   - Prompt library
   - Test execution with results
   - Performance metrics

3. **🔍 Transcript Analysis Dashboard**
   - Bulk analysis queries  
   - Search and filtering
   - Export options (JSON/CSV/Excel)
   - Multi-transcript processing

## 🔄 **Backup and Recovery**

### If something goes wrong:

1. **Revert to working version**:
   ```bash
   git log --oneline
   git checkout [last-working-commit-hash] web_app.py
   git commit -m "Revert to working version"
   git push origin b360-main
   ```

2. **Nuclear option - restore from main**:
   ```bash
   git checkout main
   cp app.py web_app.py
   git checkout b360-main
   git add web_app.py
   git commit -m "Restore from main branch"
   git push origin b360-main
   ```

## 📝 **Development Workflow**

### Daily Development:
1. Edit `app.py` locally
2. Test with: `streamlit run app.py`
3. When ready to deploy: run the deploy script

### Major Updates:
1. Create feature branch
2. Test thoroughly locally
3. Merge to b360-main
4. Sync to web_app.py
5. Deploy

## 🎉 **Success Checklist**

✅ App loads at https://ib8imbfngdgvpaj6xgnqup.streamlit.app/  
✅ "Enter Demo Mode" button works  
✅ Dashboard shows metrics and project cards  
✅ All three projects have interactive demos  
✅ File uploads work (even if simulated)  
✅ Download buttons function  
✅ Navigation between pages works  
✅ Session state persists  

---

**Last Updated**: October 3, 2025  
**Status**: ✅ WORKING PERFECTLY  
**Next Review**: When making major feature changes