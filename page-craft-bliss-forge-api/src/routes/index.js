const express = require('express')
const router = express.Router()

// Import route modules
const lpoaRoutes = require('./lpoaRoutes')
const a360ScrapingRoutes = require('./a360ScrapingRoutes')

// Health check for API
router.get('/', (req, res) => {
  res.json({
    message: 'Page Craft Bliss Forge API v1',
    version: '1.0.0',
    status: 'active',
    features: {
      lpoa: 'Laser Product Overview & Analysis',
      a360: 'A360 Scraping Management Platform'
    },
    endpoints: {
      health: '/',
      lpoa: '/api/v1/lpoa',
      a360_dashboard: '/api/v1/a360/dashboard',
      a360_brands: '/api/v1/a360/brands',
      a360_products: '/api/v1/a360/us-products',
      a360_projects: '/api/v1/a360/projects'
    }
  })
})

// Mount route modules
router.use('/lpoa', lpoaRoutes)
router.use('/a360', a360ScrapingRoutes)

module.exports = router