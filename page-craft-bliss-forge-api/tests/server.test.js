const request = require('supertest')
const app = require('../src/server')

describe('Page Craft Bliss Forge API', () => {
  describe('GET /health', () => {
    it('should return health status', async () => {
      const res = await request(app)
        .get('/health')
        .expect(200)

      expect(res.body).toHaveProperty('status', 'OK')
      expect(res.body).toHaveProperty('message', 'Page Craft Bliss Forge API is running')
      expect(res.body).toHaveProperty('timestamp')
      expect(res.body).toHaveProperty('environment')
    })
  })

  describe('GET /api/v1', () => {
    it('should return API information', async () => {
      const res = await request(app)
        .get('/api/v1')
        .expect(200)

      expect(res.body).toHaveProperty('message', 'Page Craft Bliss Forge API v1')
      expect(res.body).toHaveProperty('version', '1.0.0')
      expect(res.body).toHaveProperty('endpoints')
    })
  })

  describe('GET /nonexistent', () => {
    it('should return 404 for non-existent routes', async () => {
      const res = await request(app)
        .get('/nonexistent')
        .expect(404)

      expect(res.body).toHaveProperty('error', 'Route not found')
      expect(res.body).toHaveProperty('message')
    })
  })
})