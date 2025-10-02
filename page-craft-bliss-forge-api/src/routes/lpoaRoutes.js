/**
 * LPOA Routes
 * API routes for the Laser Parameter Optimization Assistant
 */

const express = require('express');
const router = express.Router();
const lpoaController = require('../controllers/lpoaController');

// Treatment plan generation
router.post('/generate-plan', lpoaController.generateTreatmentPlan);

// Parameter validation
router.post('/validate-parameters', lpoaController.validateParameters);

// Get optimal parameters
router.post('/optimal-parameters', lpoaController.getOptimalParameters);

// Get reference data
router.get('/treatments', lpoaController.getTreatmentModalities);
router.get('/outcomes', lpoaController.getTreatmentOutcomes);
router.get('/area-sizes', lpoaController.getAreaSizes);

module.exports = router;
