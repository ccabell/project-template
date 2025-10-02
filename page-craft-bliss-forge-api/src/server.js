const express = require('express')
const cors = require('cors')
const helmet = require('helmet')
const morgan = require('morgan')
const rateLimit = require('express-rate-limit')
const path = require('path')
require('dotenv').config()

const routes = require('./routes')
const errorHandler = require('./middleware/errorHandler')

// Initialize Express app
const app = express()

// Security middleware
app.use(helmet())

// CORS configuration
const corsOptions = {
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true,
  optionsSuccessStatus: 200
}
app.use(cors(corsOptions))

// Rate limiting
const limiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS) || 15 * 60 * 1000, // 15 minutes
  max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS) || 100, // limit each IP to 100 requests per windowMs
  message: {
    error: 'Too many requests from this IP, please try again later.'
  }
})
app.use('/api', limiter)

// Logging middleware
app.use(morgan('combined'))

// Body parsing middleware
app.use(express.json({ limit: '10mb' }))
app.use(express.urlencoded({ extended: true, limit: '10mb' }))

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'OK',
    message: 'Page Craft Bliss Forge API is running',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development'
  })
})

// Apply routes
app.use('/api/v1', routes)

// Serve static files from frontend build
const frontendPath = path.join(__dirname, '../dist/frontend')
app.use(express.static(frontendPath))

// Serve frontend for all non-API routes (SPA routing)
app.get('*', (req, res) => {
  // Don't serve SPA for API routes
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({
      error: 'API endpoint not found',
      message: `Cannot ${req.method} ${req.originalUrl}`
    })
  }
  res.sendFile(path.join(frontendPath, 'index.html'))
})

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack)
  
  const isDevelopment = process.env.NODE_ENV === 'development'
  
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
    ...(isDevelopment && { stack: err.stack })
  })
})

// Start server
const PORT = process.env.PORT || 3000
app.listen(PORT, () => {
  console.log(`🚀 Page Craft Bliss Forge API server running on port ${PORT}`)
  console.log(`📊 Health check: http://localhost:${PORT}/health`)
  console.log(`🔗 API base: http://localhost:${PORT}/api/v1`)
  console.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`)
})

module.exports = app