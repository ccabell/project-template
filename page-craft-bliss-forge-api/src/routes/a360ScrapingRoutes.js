const express = require('express')
const A360ScrapingController = require('../controllers/a360ScrapingController')

const router = express.Router()
const controller = new A360ScrapingController()

// ==================== DASHBOARD ====================
router.get('/dashboard', (req, res) => controller.getDashboard(req, res))

// ==================== BRANDS ====================
router.get('/brands', (req, res) => controller.getAllBrands(req, res))
router.post('/brands', (req, res) => controller.createBrand(req, res))
router.put('/brands/:brandId', (req, res) => controller.updateBrand(req, res))
router.delete('/brands/:brandId', (req, res) => controller.deleteBrand(req, res))

// ==================== PRODUCT CATEGORIES ====================
router.get('/product-categories', (req, res) => controller.getAllProductCategories(req, res))

// ==================== US PRODUCTS ====================
router.get('/us-products', (req, res) => controller.getAllUsProducts(req, res))
router.post('/us-products', (req, res) => controller.createUsProduct(req, res))
router.put('/us-products/:productId', (req, res) => controller.updateUsProduct(req, res))
router.delete('/us-products/:productId', (req, res) => controller.deleteUsProduct(req, res))

// ==================== SCRAPING PROJECTS ====================
router.get('/projects', (req, res) => controller.getAllScrapingProjects(req, res))
router.get('/projects/:projectId', (req, res) => controller.getScrapingProject(req, res))
router.post('/projects', (req, res) => controller.createScrapingProject(req, res))
router.put('/projects/:projectId', (req, res) => controller.updateScrapingProject(req, res))
router.delete('/projects/:projectId', (req, res) => controller.deleteScrapingProject(req, res))

// ==================== PROJECT DETAILS ====================
router.get('/projects/:projectId/pages', (req, res) => controller.getProjectPages(req, res))
router.get('/projects/:projectId/pdfs', (req, res) => controller.getProjectPdfs(req, res))
router.get('/projects/:projectId/chunks', (req, res) => controller.getProjectContentChunks(req, res))
router.get('/projects/:projectId/activities', (req, res) => controller.getProjectActivities(req, res))
router.post('/projects/:projectId/notes', (req, res) => controller.addProjectNote(req, res))

// ==================== IMPORT ====================
router.post('/import/crawl-results', (req, res) => controller.importCrawlResults(req, res))

module.exports = router