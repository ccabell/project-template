const A360ScrapingService = require('../services/a360ScrapingService')

/**
 * A360 Scraping Management Controller
 * Handles HTTP requests for the scraping management system
 */
class A360ScrapingController {
  constructor() {
    this.scrapingService = new A360ScrapingService()
  }

  // ==================== DASHBOARD ====================

  async getDashboard(req, res) {
    try {
      const stats = await this.scrapingService.getDashboardStats()
      const recentActivity = await this.scrapingService.getRecentActivity(10)

      if (!stats.success) {
        return res.status(500).json({ success: false, error: stats.error })
      }

      res.json({
        success: true,
        data: {
          stats: stats.data,
          recent_activity: recentActivity.success ? recentActivity.data : []
        }
      })
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  // ==================== BRANDS ====================

  async getAllBrands(req, res) {
    try {
      const result = await this.scrapingService.getAllBrands()
      if (!result.success) {
        return res.status(500).json(result)
      }
      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async createBrand(req, res) {
    try {
      const { name, description, website_url, logo_url, color_hex } = req.body

      if (!name) {
        return res.status(400).json({ success: false, error: 'Brand name is required' })
      }

      const brandData = {
        name,
        description,
        website_url,
        logo_url,
        color_hex: color_hex || '#3B82F6'
      }

      const result = await this.scrapingService.createBrand(brandData)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.status(201).json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async updateBrand(req, res) {
    try {
      const { brandId } = req.params
      const updateData = req.body

      const result = await this.scrapingService.updateBrand(brandId, updateData)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async deleteBrand(req, res) {
    try {
      const { brandId } = req.params

      const result = await this.scrapingService.deleteBrand(brandId)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  // ==================== PRODUCT CATEGORIES ====================

  async getAllProductCategories(req, res) {
    try {
      const result = await this.scrapingService.getAllProductCategories()
      if (!result.success) {
        return res.status(500).json(result)
      }
      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  // ==================== US PRODUCTS ====================

  async getAllUsProducts(req, res) {
    try {
      const filters = {
        brand_id: req.query.brand_id,
        category_id: req.query.category_id,
        status: req.query.status,
        priority_level: req.query.priority_level ? parseInt(req.query.priority_level) : undefined
      }

      // Remove undefined values
      Object.keys(filters).forEach(key => filters[key] === undefined && delete filters[key])

      const result = await this.scrapingService.getAllUsProducts(filters)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async createUsProduct(req, res) {
    try {
      const {
        brand_id,
        category_id,
        name,
        generic_name,
        product_code,
        fda_approval_date,
        indication,
        description,
        priority_level,
        status,
        official_website,
        prescribing_info_url
      } = req.body

      if (!brand_id || !name) {
        return res.status(400).json({
          success: false,
          error: 'Brand ID and product name are required'
        })
      }

      const productData = {
        brand_id,
        category_id,
        name,
        generic_name,
        product_code,
        fda_approval_date,
        indication,
        description,
        priority_level: priority_level || 3,
        status: status || 'pending',
        official_website,
        prescribing_info_url
      }

      const result = await this.scrapingService.createUsProduct(productData)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.status(201).json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async updateUsProduct(req, res) {
    try {
      const { productId } = req.params
      const updateData = req.body

      const result = await this.scrapingService.updateUsProduct(productId, updateData)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async deleteUsProduct(req, res) {
    try {
      const { productId } = req.params

      const result = await this.scrapingService.deleteUsProduct(productId)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  // ==================== SCRAPING PROJECTS ====================

  async getAllScrapingProjects(req, res) {
    try {
      const filters = {
        brand_id: req.query.brand_id,
        product_id: req.query.product_id,
        status: req.query.status,
        project_type: req.query.project_type
      }

      // Remove undefined values
      Object.keys(filters).forEach(key => filters[key] === undefined && delete filters[key])

      const result = await this.scrapingService.getAllScrapingProjects(filters)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async getScrapingProject(req, res) {
    try {
      const { projectId } = req.params

      const result = await this.scrapingService.getScrapingProject(projectId)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async createScrapingProject(req, res) {
    try {
      const {
        name,
        brand_id,
        product_id,
        base_url,
        project_type,
        priority,
        scraping_method,
        max_pages,
        max_depth,
        include_pdfs,
        custom_config,
        assigned_to,
        notes,
        tags
      } = req.body

      if (!name || !base_url) {
        return res.status(400).json({
          success: false,
          error: 'Project name and base URL are required'
        })
      }

      const projectData = {
        name,
        brand_id,
        product_id,
        base_url,
        project_type: project_type || 'product_site',
        priority: priority || 3,
        scraping_method: scraping_method || 'firecrawl',
        max_pages: max_pages || 100,
        max_depth: max_depth || 3,
        include_pdfs: include_pdfs !== false,
        custom_config,
        assigned_to,
        notes,
        tags
      }

      const result = await this.scrapingService.createScrapingProject(projectData)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.status(201).json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async updateScrapingProject(req, res) {
    try {
      const { projectId } = req.params
      const updateData = req.body

      const result = await this.scrapingService.updateScrapingProject(projectId, updateData)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async deleteScrapingProject(req, res) {
    try {
      const { projectId } = req.params

      const result = await this.scrapingService.deleteScrapingProject(projectId)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  // ==================== PROJECT DETAILS ====================

  async getProjectPages(req, res) {
    try {
      const { projectId } = req.params
      const limit = parseInt(req.query.limit) || 100

      const result = await this.scrapingService.getProjectPages(projectId, limit)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async getProjectPdfs(req, res) {
    try {
      const { projectId } = req.params
      const limit = parseInt(req.query.limit) || 100

      const result = await this.scrapingService.getProjectPdfs(projectId, limit)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async getProjectContentChunks(req, res) {
    try {
      const { projectId } = req.params
      const limit = parseInt(req.query.limit) || 500

      const result = await this.scrapingService.getProjectContentChunks(projectId, limit)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async getProjectActivities(req, res) {
    try {
      const { projectId } = req.params
      const limit = parseInt(req.query.limit) || 50

      const result = await this.scrapingService.getProjectActivities(projectId, limit)
      if (!result.success) {
        return res.status(500).json(result)
      }

      res.json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  async addProjectNote(req, res) {
    try {
      const { projectId } = req.params
      const { note, user_name } = req.body

      if (!note) {
        return res.status(400).json({
          success: false,
          error: 'Note content is required'
        })
      }

      const result = await this.scrapingService.logProjectActivity(
        projectId,
        'note_added',
        note,
        null,
        user_name || 'Anonymous'
      )

      if (!result.success) {
        return res.status(500).json(result)
      }

      res.status(201).json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }

  // ==================== IMPORT ====================

  async importCrawlResults(req, res) {
    try {
      const { crawl_data, project_name, brand_id, product_id } = req.body

      if (!crawl_data || !project_name || !brand_id) {
        return res.status(400).json({
          success: false,
          error: 'Crawl data, project name, and brand ID are required'
        })
      }

      const result = await this.scrapingService.importCrawlResultsAsProject(
        crawl_data,
        project_name,
        brand_id,
        product_id
      )

      if (!result.success) {
        return res.status(500).json(result)
      }

      res.status(201).json(result)
    } catch (error) {
      res.status(500).json({ success: false, error: error.message })
    }
  }
}

module.exports = A360ScrapingController