# 🚀 A360 Project Hub - Quick Reference

## ⚡ **IMMEDIATE DEPLOYMENT**
```bash
# Double-click this file to deploy:
deploy_app.bat
```

## 🔗 **IMPORTANT LINKS**
- **Live App**: https://ib8imbfngdgvpaj6xgnqup.streamlit.app/
- **Manage App**: https://share.streamlit.io/ (find your app)
- **Repository**: https://github.com/ccabell/project-template

## ⚙️ **CRITICAL SETTINGS** (Never Change)
- **Repository**: `ccabell/project-template`
- **Branch**: `b360-main`
- **Main File**: `web_app.py`

## 📁 **FILE ROLES**
- `app.py` → **Edit this file** (main development)
- `web_app.py` → **Deployment file** (auto-synced)
- `deploy_app.bat` → **One-click deploy script**

## 🛠️ **QUICK FIXES**

### Site Shows Old Content?
```bash
deploy_app.bat
```

### Emergency Reset?
```bash
cp app.py web_app.py
git add web_app.py
git commit -m "Emergency sync"
git push origin b360-main
```

### Something Broken?
1. Go to Streamlit Cloud → "Manage app" → "Reboot app"
2. Wait 60 seconds
3. Refresh browser

## ✅ **SUCCESS CHECKLIST**
- [ ] Site loads: https://ib8imbfngdgvpaj6xgnqup.streamlit.app/
- [ ] "Enter Demo Mode" works
- [ ] Dashboard shows metrics
- [ ] All 3 projects have demos
- [ ] Navigation works

## 🆘 **HELP**
- Check `STREAMLIT_DEPLOYMENT.md` for detailed troubleshooting
- Look at `DEPLOYMENT_CONFIG.json` for technical settings
- Review Streamlit Cloud logs in "Manage app"

---
**Last Updated**: Oct 3, 2025 | **Status**: ✅ WORKING