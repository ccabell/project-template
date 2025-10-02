const errorHandler = (err, req, res, next) => {
  let error = { ...err }
  error.message = err.message

  console.error(err.stack)

  // Mongoose bad ObjectId
  if (err.name === 'CastError') {
    const message = 'Resource not found'
    error = { message, status: 404 }
  }

  // Mongoose duplicate key
  if (err.code === 11000) {
    const message = 'Duplicate field value entered'
    error = { message, status: 400 }
  }

  // Mongoose validation error
  if (err.name === 'ValidationError') {
    const message = Object.values(err.errors).map(val => val.message).join(', ')
    error = { message, status: 400 }
  }

  // JWT errors
  if (err.name === 'JsonWebTokenError') {
    const message = 'Invalid token'
    error = { message, status: 401 }
  }

  if (err.name === 'TokenExpiredError') {
    const message = 'Token expired'
    error = { message, status: 401 }
  }

  const isDevelopment = process.env.NODE_ENV === 'development'

  res.status(error.status || 500).json({
    success: false,
    error: error.message || 'Server Error',
    ...(isDevelopment && { stack: err.stack })
  })
}

module.exports = errorHandler