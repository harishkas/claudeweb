# 🚀 HAKS SHOP - Deployment Guide

## Overview
This guide will help you deploy your scalable e-commerce website to production.

---

## 📋 Prerequisites

1. **Render Account** (or AWS/Heroku/DigitalOcean)
2. **Database** (PostgreSQL)
3. **Redis** (Optional but recommended for caching)
4. **Git** installed
5. **GitHub/GitLab** account

---

## 🎯 Quick Start - Deploy to Render

### Step 1: Setup Database

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New" → "PostgreSQL"
3. Name: `haksshop-db`
4. Choose free tier or paid plan
5. Click "Create Database"
6. **Copy the Internal Database URL** (starts with `postgresql://`)

### Step 2: Setup Redis (Optional but Recommended)

1. In Render Dashboard, click "New" → "Redis"
2. Name: `haksshop-cache`
3. Choose free tier
4. Click "Create Redis"
5. **Copy the Redis URL** (starts with `redis://`)

### Step 3: Deploy Backend

1. Push your code to GitHub:
```bash
git init
git add .
git commit -m "Initial commit - Scalable HAKS Shop"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/haksshop.git
git push -u origin main
```

2. In Render Dashboard, click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name:** `haksshop-backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** Free or Starter

5. **Add Environment Variables:**
   Click "Advanced" → "Add Environment Variable"
   
   ```
   SECRET_KEY = [Generate a random 32-character string]
   DATABASE_URL = [Paste your PostgreSQL Internal URL from Step 1]
   REDIS_URL = [Paste your Redis URL from Step 2]
   ```

6. Click "Create Web Service"
7. **Wait 3-5 minutes** for deployment
8. **Copy your backend URL** (e.g., `https://haksshop-backend.onrender.com`)

### Step 4: Initialize Database

1. In Render Dashboard, go to your PostgreSQL service
2. Click "Shell" tab
3. Paste your `schema.sql` content and execute
4. Or use a tool like **TablePlus** or **pgAdmin** to connect and run the schema

### Step 5: Deploy Frontend

#### Option A: Deploy to Render (Static Site)

1. In Render Dashboard, click "New" → "Static Site"
2. Connect your GitHub repository
3. Configure:
   - **Name:** `haksshop-frontend`
   - **Build Command:** `echo "No build needed"`
   - **Publish Directory:** `.` (root directory)
4. Click "Create Static Site"

#### Option B: Deploy to Netlify/Vercel

1. Go to [Netlify](https://netlify.com) or [Vercel](https://vercel.com)
2. Import your repository
3. Deploy with default settings

### Step 6: Update Frontend Configuration

1. Open `js/main.js` (or wherever you deploy it)
2. Update the API_BASE URL:
   ```javascript
   const API_BASE = "https://haksshop-backend.onrender.com";
   ```
3. Commit and push changes

---

## ⚙️ Configuration Checklist

### Required Environment Variables
- ✅ `SECRET_KEY` - Random secure string
- ✅ `DATABASE_URL` - PostgreSQL connection string
- ✅ `REDIS_URL` - Redis connection string (optional)

### Optional Environment Variables
- `PORT` - Default: 5000
- `JWT_EXPIRATION_HOURS` - Default: 24
- `ALLOWED_ORIGINS` - CORS origins

---

## 🔒 Security Best Practices

1. **Generate Strong SECRET_KEY:**
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```

2. **Enable HTTPS:** Render does this automatically

3. **Set CORS Properly:**
   Update `flask_cors` in `app.py` to only allow your frontend domain

4. **Change Admin Password:**
   After first deployment, login to admin panel and change the default password

5. **Environment Variables:**
   Never commit `.env` file to Git
   Always use environment variables for secrets

---

## 📊 Database Setup

Run this SQL after creating your PostgreSQL database:

1. Connect to your database using the connection string
2. Execute the `schema.sql` file
3. The schema includes:
   - All tables with proper indexes
   - Sample admin user (email: admin@haksshop.com, password: admin123)
   - Sample products
   - Performance optimizations

**⚠️ Change the admin password immediately after first login!**

---

## 🧪 Testing Your Deployment

### Backend Health Check
```bash
curl https://your-backend-url.onrender.com/health
```

Expected response:
```json
{
  "database": "healthy",
  "redis": "healthy"
}
```

### Test Product API
```bash
curl https://your-backend-url.onrender.com/products
```

### Test Frontend
1. Open your frontend URL
2. Try signing up
3. Try logging in
4. Try adding products to cart
5. Check admin panel

---

## 📈 Performance Optimizations Included

✅ **Database Connection Pooling** (5-20 connections)
✅ **Redis Caching** (10-minute cache for products)
✅ **Database Indexes** (10x faster queries)
✅ **Rate Limiting** (Prevents abuse)
✅ **Pagination** (20 products per page)
✅ **Lazy Loading** (Images load as needed)
✅ **Error Handling** (Graceful error recovery)
✅ **Logging** (Track issues in production)

---

## 🐛 Troubleshooting

### Issue: "Database connection failed"
**Solution:** 
- Check DATABASE_URL is correct
- Ensure database is running
- Check firewall settings

### Issue: "Redis connection failed"
**Solution:**
- Redis is optional - app will work without it
- Check REDIS_URL is correct
- Ensure Redis instance is running

### Issue: "500 Internal Server Error"
**Solution:**
- Check logs in Render Dashboard
- Look at `/logs/app.log` for errors
- Verify all environment variables are set

### Issue: "CORS error in browser"
**Solution:**
- Update CORS settings in `app.py`
- Add your frontend domain to allowed origins

---

## 📱 Monitoring & Maintenance

### View Logs
Render Dashboard → Your Service → Logs tab

### Monitor Performance
- Check "Metrics" tab in Render Dashboard
- Response times should be < 500ms
- Error rate should be < 0.1%

### Database Maintenance
Run this monthly:
```sql
VACUUM ANALYZE;
```

### Cache Refresh
Products are cached for 10 minutes. To force refresh:
- Add/edit/delete a product in admin panel
- Or clear Redis cache

---

## 🎉 You're Done!

Your scalable e-commerce website is now live!

**Next Steps:**
1. Share your website URL
2. Monitor performance in Render Dashboard
3. Add more products via admin panel
4. Consider upgrading to paid plans for:
   - Better performance
   - More concurrent users
   - Dedicated resources

---

## 📞 Need Help?

- **Backend Issues:** Check logs in Render Dashboard
- **Database Issues:** Use TablePlus or pgAdmin to inspect
- **Frontend Issues:** Check browser console
- **Performance Issues:** Review metrics in dashboard

---

## 🚀 Scaling Further

When you outgrow the current setup:

1. **Upgrade Database:** Switch to larger PostgreSQL plan
2. **Upgrade Redis:** Get dedicated Redis instance
3. **Add CDN:** Use Cloudflare for static assets
4. **Multiple Regions:** Deploy in multiple locations
5. **Load Balancer:** Distribute traffic across instances

---

**Built with ❤️ for scalability and performance**
