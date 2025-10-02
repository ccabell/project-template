# A360 Scraping Management Platform

A comprehensive web interface to track all your A360 scraping projects across pharmaceutical brands like Allergan, Galderma, Revance, Merz, and more.

## 🌟 Features

- **Multi-Brand Dashboard** - Track scraping across all pharmaceutical brands
- **Master Product Checklist** - Monitor US products and their scraping status  
- **Project Management** - Create, track, and manage scraping projects
- **Real-time Analytics** - View progress, statistics, and completion rates
- **PDF Integration** - Track PDF downloads and content extraction
- **Cloud Deployment** - Powered by Supabase for scalable hosting

## 🏗️ Architecture

- **Backend**: Node.js + Express + Supabase
- **Frontend**: React + TypeScript + Tailwind CSS  
- **Database**: PostgreSQL (via Supabase)
- **API**: RESTful endpoints for all operations
- **Deployment**: Single full-stack application

## 🚀 Quick Start

### 1. Set Up Supabase Database

1. Go to your [Supabase Dashboard](https://supabase.com/dashboard)
2. Navigate to SQL Editor
3. Run the schema from `database/supabase-schema.sql`
4. Verify tables are created: `brands`, `us_products`, `scraping_projects`, etc.

### 2. Install Dependencies

```bash
npm install
```

### 3. Start Development

```bash
# Start backend API server (port 5000)
npm run dev

# In another terminal, start frontend dev server (port 3000)
npm run dev:frontend
```

### 4. Import Your CoolSculpting Data

```bash
npm run import:coolsculpting
```

### 5. Access the Dashboard

- **Web Interface**: http://localhost:3000
- **API Endpoints**: http://localhost:5000/api/v1
- **Health Check**: http://localhost:5000/health

## 📊 Dashboard Features

### Overview Dashboard
- Total brands, products, and projects
- Completion statistics and progress tracking
- Brand-wise breakdowns and analytics

### Products Master List
- Complete US pharmaceutical products database
- Status tracking: Pending → In Progress → Scraped
- Priority levels and filtering
- Brand and category organization

### Projects Management  
- Active scraping projects tracking
- Progress monitoring (pages, words, PDFs)
- Status updates and timeline
- Brand and product associations

### Brands Overview
- All pharmaceutical companies
- Product counts and completion rates
- Project statistics per brand
- Brand-specific color coding

## 🔌 API Endpoints

### Dashboard
- `GET /api/v1/a360/dashboard` - Dashboard statistics and analytics

### Brands Management
- `GET /api/v1/a360/brands` - List all brands
- `POST /api/v1/a360/brands` - Create new brand
- `PUT /api/v1/a360/brands/:id` - Update brand
- `DELETE /api/v1/a360/brands/:id` - Delete brand

### Products Management
- `GET /api/v1/a360/us-products` - List US products (with filters)
- `POST /api/v1/a360/us-products` - Create new product
- `PUT /api/v1/a360/us-products/:id` - Update product
- `DELETE /api/v1/a360/us-products/:id` - Delete product

### Projects Management
- `GET /api/v1/a360/projects` - List scraping projects (with filters)
- `GET /api/v1/a360/projects/:id` - Get project details
- `POST /api/v1/a360/projects` - Create new project
- `PUT /api/v1/a360/projects/:id` - Update project
- `DELETE /api/v1/a360/projects/:id` - Delete project

### Project Data
- `GET /api/v1/a360/projects/:id/pages` - Get scraped pages
- `GET /api/v1/a360/projects/:id/pdfs` - Get PDF files  
- `GET /api/v1/a360/projects/:id/chunks` - Get content chunks (for RAG)
- `GET /api/v1/a360/projects/:id/activities` - Get project activity log

### Import & Integration
- `POST /api/v1/a360/import/crawl-results` - Import crawl data as project

## 🛠️ Development Scripts

```bash
# Backend development
npm run dev              # Start backend with nodemon
npm start               # Start production backend

# Frontend development  
npm run dev:frontend    # Start React dev server
npm run build:frontend  # Build React for production
npm run preview:frontend # Preview production build

# Full stack
npm run build           # Build frontend + start backend
npm test               # Run tests
npm run lint           # Lint code

# Database & Import
npm run setup:supabase  # Show setup instructions
npm run import:coolsculpting # Import CoolSculpting data
```

## 🌐 Deployment

### Build for Production

```bash
npm run build:frontend  # Build React app
npm start               # Start production server
```

The server will serve the built React app on the same port as the API.

### Environment Variables

Create `.env` file:

```env
NODE_ENV=production
PORT=5000
CORS_ORIGIN=https://yourdomain.com

# Rate limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

### Hosting Options

1. **Supabase + Vercel/Netlify** - Deploy frontend statically, backend as functions
2. **Railway/Render** - Deploy as single full-stack app
3. **AWS/GCP/Azure** - Deploy with container or VM
4. **Self-hosted** - Run on your own server

## 📁 Project Structure

```
src/
├── config/
│   └── supabase.js           # Supabase client configuration
├── controllers/
│   └── a360ScrapingController.js # HTTP request handlers
├── services/  
│   └── a360ScrapingService.js # Business logic and database operations
├── routes/
│   └── a360ScrapingRoutes.js  # API route definitions
├── scripts/
│   └── importCoolSculptingData.js # Data import utilities
├── frontend/                  # React application
│   ├── App.tsx               # Main React component
│   ├── index.css             # Tailwind CSS styles
│   ├── main.tsx              # React entry point
│   └── index.html            # HTML template
└── server.js                 # Express server with static file serving

database/
└── supabase-schema.sql       # Complete database schema

dist/frontend/                # Built React app (generated)
```

## 🎯 Usage Examples

### Adding a New Brand

```javascript
// Via API
const response = await fetch('/api/v1/a360/brands', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Botox Medical',
    description: 'Medical aesthetics and neurotoxins',
    website_url: 'https://botoxmedical.com',
    color_hex: '#1E40AF'
  })
})
```

### Creating a Scraping Project

```javascript
const project = await fetch('/api/v1/a360/projects', {
  method: 'POST', 
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Botox Official Website Scrape',
    brand_id: 'brand-uuid-here',
    base_url: 'https://botoxcosmetic.com',
    priority: 1,
    max_pages: 100,
    include_pdfs: true
  })
})
```

### Importing Crawl Results

```javascript
const importResult = await fetch('/api/v1/a360/import/crawl-results', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    crawl_data: {
      domain: 'botoxcosmetic.com',
      total_pages: 45,
      total_words: 67890,
      pdf_links_found: ['https://botox.com/safety.pdf']
    },
    project_name: 'Botox Website Import',
    brand_id: 'allergan-brand-uuid'
  })
})
```

## 🔒 Security Features

- Row Level Security (RLS) enabled on all tables
- API rate limiting (100 requests per 15 minutes)
- CORS configuration for secure cross-origin requests
- Input validation and sanitization
- Secure file upload and storage paths

## 📈 Analytics & Monitoring

The dashboard provides comprehensive analytics:

- **Completion Rates** - Track % of products scraped per brand
- **Project Progress** - Monitor active scraping projects
- **Content Statistics** - Pages, words, PDFs across all projects
- **Brand Comparisons** - Side-by-side progress tracking
- **Timeline Views** - Historical progress and activity logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-brand-tracker`
3. Make your changes and test thoroughly
4. Commit: `git commit -am 'Add new brand tracking feature'`
5. Push: `git push origin feature/new-brand-tracker`
6. Submit a Pull Request

## 📝 License

MIT License - see LICENSE file for details.

## 🆘 Support

For issues or questions:

1. Check existing GitHub issues
2. Create a new issue with detailed description
3. Include error logs and reproduction steps
4. Specify your environment (OS, Node version, etc.)

---

**Built for A360** - Comprehensive pharmaceutical scraping management platform