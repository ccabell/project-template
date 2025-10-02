const mongoose = require('mongoose')

const connectDatabase = async () => {
  try {
    const conn = await mongoose.connect(process.env.DATABASE_URL || 'mongodb://localhost:27017/page-craft-bliss-forge', {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    })

    console.log(`📦 MongoDB Connected: ${conn.connection.host}:${conn.connection.port}`)
    console.log(`🗄️  Database: ${conn.connection.name}`)
    
    return conn
  } catch (error) {
    console.error('❌ Database connection error:', error.message)
    process.exit(1)
  }
}

const disconnectDatabase = async () => {
  try {
    await mongoose.disconnect()
    console.log('📦 MongoDB Disconnected')
  } catch (error) {
    console.error('❌ Database disconnection error:', error.message)
  }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n📦 Shutting down database connection...')
  await disconnectDatabase()
  process.exit(0)
})

module.exports = {
  connectDatabase,
  disconnectDatabase
}