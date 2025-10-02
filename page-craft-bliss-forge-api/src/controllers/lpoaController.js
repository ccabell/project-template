/**
 * LPOA Controller
 * Handles HTTP requests for the Laser Parameter Optimization Assistant
 */

const lpoaService = require('../services/lpoaService');

/**
 * Generate a comprehensive treatment plan
 * POST /api/lpoa/generate-plan
 */
async function generateTreatmentPlan(req, res) {
  try {
    const patientData = req.body;

    // Validate required fields
    if (!patientData.skinType || !patientData.treatmentType) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: skinType and treatmentType are required'
      });
    }

    const treatmentPlan = lpoaService.generateTreatmentPlan(patientData);

    res.json({
      success: true,
      data: treatmentPlan
    });
  } catch (error) {
    console.error('Error generating treatment plan:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to generate treatment plan'
    });
  }
}

/**
 * Validate treatment parameters
 * POST /api/lpoa/validate-parameters
 */
async function validateParameters(req, res) {
  try {
    const { params, treatmentType, skinType, riskFactors } = req.body;

    if (!params || !treatmentType || !skinType) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: params, treatmentType, and skinType are required'
      });
    }

    const validation = lpoaService.validateTreatmentParameters(
      params,
      treatmentType,
      skinType,
      riskFactors || []
    );

    res.json({
      success: true,
      data: validation
    });
  } catch (error) {
    console.error('Error validating parameters:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to validate parameters'
    });
  }
}

/**
 * Get optimal parameters for a treatment
 * POST /api/lpoa/optimal-parameters
 */
async function getOptimalParameters(req, res) {
  try {
    const { treatmentType, skinType, riskFactors } = req.body;

    if (!treatmentType || !skinType) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: treatmentType and skinType are required'
      });
    }

    const optimalParams = lpoaService.getOptimalParameters(
      treatmentType,
      skinType,
      riskFactors || []
    );

    if (!optimalParams) {
      return res.status(400).json({
        success: false,
        error: 'Invalid treatment type or skin type'
      });
    }

    res.json({
      success: true,
      data: optimalParams
    });
  } catch (error) {
    console.error('Error getting optimal parameters:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to get optimal parameters'
    });
  }
}

/**
 * Get available treatment modalities
 * GET /api/lpoa/treatments
 */
async function getTreatmentModalities(req, res) {
  try {
    res.json({
      success: true,
      data: lpoaService.TREATMENT_MODALITIES
    });
  } catch (error) {
    console.error('Error getting treatment modalities:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to get treatment modalities'
    });
  }
}

/**
 * Get treatment outcomes data
 * GET /api/lpoa/outcomes
 */
async function getTreatmentOutcomes(req, res) {
  try {
    res.json({
      success: true,
      data: lpoaService.TREATMENT_OUTCOMES
    });
  } catch (error) {
    console.error('Error getting treatment outcomes:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to get treatment outcomes'
    });
  }
}

/**
 * Get area sizes
 * GET /api/lpoa/area-sizes
 */
async function getAreaSizes(req, res) {
  try {
    res.json({
      success: true,
      data: lpoaService.AREA_SIZES
    });
  } catch (error) {
    console.error('Error getting area sizes:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Failed to get area sizes'
    });
  }
}

module.exports = {
  generateTreatmentPlan,
  validateParameters,
  getOptimalParameters,
  getTreatmentModalities,
  getTreatmentOutcomes,
  getAreaSizes
};
