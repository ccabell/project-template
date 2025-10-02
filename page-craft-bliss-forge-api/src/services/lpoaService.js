/**
 * Laser Parameter Optimization Assistant (LPOA) Service
 * 
 * Core service for generating comprehensive, AI-powered treatment plans
 * with optimal laser parameters, safety validation, and cost estimation.
 */

const {
  validateParameters,
  getOptimalParameters,
  TREATMENT_MODALITIES,
  SKIN_TYPES,
  RISK_FACTORS
} = require('../config/laserSafetyMatrix');

/**
 * Treatment outcome data for cost and session estimation
 */
const TREATMENT_OUTCOMES = {
  BBL_PHOTOREJUVENATION: {
    avgSessions: { min: 3, max: 6, typical: 4 },
    sessionInterval: { weeks: 3, description: '3-4 weeks apart' },
    clearanceRate: { single: 0.25, cumulative: 0.85 },
    costPerSession: { min: 300, max: 600, avg: 450 }
  },
  LASER_HAIR_REMOVAL: {
    avgSessions: { min: 6, max: 10, typical: 8 },
    sessionInterval: { weeks: 6, description: '6-8 weeks apart' },
    clearanceRate: { single: 0.15, cumulative: 0.90 },
    costPerSession: { min: 200, max: 500, avg: 350 },
    maintenanceRequired: true,
    maintenanceInterval: { months: 12 }
  },
  FRACTIONAL_RESURFACING: {
    avgSessions: { min: 1, max: 3, typical: 2 },
    sessionInterval: { weeks: 4, description: '4-6 weeks apart' },
    clearanceRate: { single: 0.40, cumulative: 0.80 },
    costPerSession: { min: 800, max: 2000, avg: 1200 },
    downtimeRequired: true,
    downtimeDays: { min: 5, max: 10 }
  },
  VASCULAR_TREATMENT: {
    avgSessions: { min: 2, max: 5, typical: 3 },
    sessionInterval: { weeks: 4, description: '4-6 weeks apart' },
    clearanceRate: { single: 0.30, cumulative: 0.75 },
    costPerSession: { min: 400, max: 800, avg: 600 }
  }
};

/**
 * Area size multipliers for treatment areas
 */
const AREA_SIZES = {
  small: { multiplier: 1.0, description: 'Small area (upper lip, between brows)', examples: ['upper_lip', 'glabella'] },
  medium: { multiplier: 1.5, description: 'Medium area (full face, underarms)', examples: ['full_face', 'underarms', 'bikini'] },
  large: { multiplier: 2.0, description: 'Large area (back, legs)', examples: ['back', 'full_legs', 'chest'] },
  xlarge: { multiplier: 3.0, description: 'Extra large area (full body zones)', examples: ['full_body'] }
};

/**
 * Generates a comprehensive treatment plan
 * @param {Object} patientData - Patient information and treatment request
 * @returns {Object} Complete treatment plan with parameters, safety info, and cost estimation
 */
function generateTreatmentPlan(patientData) {
  const {
    skinType,
    treatmentType,
    treatmentArea,
    areaSize = 'medium',
    indication,
    riskFactors = [],
    previousTreatments = [],
    patientAge,
    patientConcerns = []
  } = patientData;

  // Validate inputs
  if (!skinType || skinType < 1 || skinType > 6) {
    throw new Error('Invalid skin type. Must be 1-6 (Fitzpatrick scale)');
  }

  if (!TREATMENT_MODALITIES[treatmentType]) {
    throw new Error(`Invalid treatment type: ${treatmentType}`);
  }

  // Get optimal parameters
  const optimalParams = getOptimalParameters(treatmentType, skinType, riskFactors);
  
  if (!optimalParams) {
    throw new Error('Could not generate optimal parameters');
  }

  // Generate session plan
  const sessionPlan = generateSessionPlan(
    treatmentType,
    skinType,
    indication,
    previousTreatments
  );

  // Calculate cost estimation
  const costEstimate = calculateCostEstimate(
    treatmentType,
    sessionPlan.totalSessions,
    areaSize
  );

  // Generate safety recommendations
  const safetyRecommendations = generateSafetyRecommendations(
    skinType,
    riskFactors,
    treatmentType,
    optimalParams
  );

  // Generate clinical approach
  const clinicalApproach = generateClinicalApproach(
    treatmentType,
    skinType,
    indication,
    patientAge,
    patientConcerns
  );

  // Generate pre and post treatment protocols
  const treatmentProtocols = generateTreatmentProtocols(
    treatmentType,
    skinType,
    riskFactors
  );

  return {
    planId: generatePlanId(),
    generatedAt: new Date().toISOString(),
    patient: {
      skinType,
      skinTypeDescription: getSkinTypeDescription(skinType),
      riskFactors: riskFactors.map(rf => ({
        factor: rf,
        description: RISK_FACTORS[rf]?.description || rf
      }))
    },
    treatment: {
      type: treatmentType,
      name: TREATMENT_MODALITIES[treatmentType].name,
      indication,
      area: treatmentArea,
      areaSize
    },
    optimalParameters: optimalParams,
    sessionPlan,
    costEstimate,
    safetyRecommendations,
    clinicalApproach,
    protocols: treatmentProtocols,
    pdfReferences: generatePDFReferences(treatmentType),
    disclaimer: 'This treatment plan is generated based on manufacturer guidelines and clinical best practices. Always use clinical judgment and adjust parameters based on individual patient response. Monitor patients closely during and after treatment.'
  };
}

/**
 * Generates session plan with timeline
 */
function generateSessionPlan(treatmentType, skinType, indication, previousTreatments) {
  const outcomeData = TREATMENT_OUTCOMES[treatmentType];
  
  // Adjust sessions based on skin type and previous treatments
  let recommendedSessions = outcomeData.avgSessions.typical;
  
  if (skinType > 4) {
    recommendedSessions += 1; // Darker skin may require more sessions
  }
  
  if (previousTreatments.length > 0) {
    recommendedSessions -= 1; // Previous treatments may reduce required sessions
  }

  const sessions = [];
  for (let i = 1; i <= recommendedSessions; i++) {
    const weekOffset = (i - 1) * outcomeData.sessionInterval.weeks;
    sessions.push({
      sessionNumber: i,
      weekFromStart: weekOffset,
      expectedClearance: Math.min(
        outcomeData.clearanceRate.single * i * 1.1,
        outcomeData.clearanceRate.cumulative
      ).toFixed(2),
      notes: i === 1 ? 'Start conservative, assess response' : 
             i === recommendedSessions ? 'Final session, evaluate results' :
             'Adjust parameters based on previous response'
    });
  }

  return {
    totalSessions: recommendedSessions,
    sessionInterval: outcomeData.sessionInterval.description,
    expectedDuration: {
      weeks: (recommendedSessions - 1) * outcomeData.sessionInterval.weeks,
      months: Math.ceil(((recommendedSessions - 1) * outcomeData.sessionInterval.weeks) / 4)
    },
    sessions,
    maintenanceRequired: outcomeData.maintenanceRequired || false,
    maintenanceInterval: outcomeData.maintenanceInterval,
    expectedClearanceRate: (outcomeData.clearanceRate.cumulative * 100).toFixed(0) + '%'
  };
}

/**
 * Calculates cost estimation for treatment plan
 */
function calculateCostEstimate(treatmentType, totalSessions, areaSize) {
  const outcomeData = TREATMENT_OUTCOMES[treatmentType];
  const areaMultiplier = AREA_SIZES[areaSize]?.multiplier || 1.5;
  
  const basePerSession = outcomeData.costPerSession.avg;
  const adjustedPerSession = Math.round(basePerSession * areaMultiplier);
  
  const totalCost = adjustedPerSession * totalSessions;
  const minCost = Math.round(outcomeData.costPerSession.min * areaMultiplier * totalSessions);
  const maxCost = Math.round(outcomeData.costPerSession.max * areaMultiplier * totalSessions);

  return {
    perSession: {
      estimated: adjustedPerSession,
      range: {
        min: Math.round(outcomeData.costPerSession.min * areaMultiplier),
        max: Math.round(outcomeData.costPerSession.max * areaMultiplier)
      }
    },
    total: {
      estimated: totalCost,
      range: { min: minCost, max: maxCost }
    },
    areaSize: AREA_SIZES[areaSize]?.description,
    currency: 'USD',
    note: 'Costs are estimates and may vary by location, provider expertise, and facility overhead'
  };
}

/**
 * Generates safety recommendations based on patient profile
 */
function generateSafetyRecommendations(skinType, riskFactors, treatmentType, optimalParams) {
  const recommendations = [];

  // Skin type specific recommendations
  if (skinType >= 4) {
    recommendations.push({
      category: 'Skin Type Safety',
      priority: 'HIGH',
      recommendation: 'Darker skin types (IV-VI) require careful parameter selection to avoid post-inflammatory hyperpigmentation',
      action: 'Start with conservative settings and test spot recommended'
    });
  }

  // Risk factor recommendations
  if (riskFactors.includes('RECENT_SUN_EXPOSURE')) {
    recommendations.push({
      category: 'Sun Exposure',
      priority: 'CRITICAL',
      recommendation: 'Recent sun exposure increases burn risk',
      action: 'Delay treatment by 2-4 weeks or reduce fluence by 20%'
    });
  }

  if (riskFactors.includes('ACTIVE_ACNE')) {
    recommendations.push({
      category: 'Active Acne',
      priority: 'HIGH',
      recommendation: 'Active acne increases inflammation risk',
      action: 'Treat acne first or avoid active lesions during treatment'
    });
  }

  // Treatment-specific recommendations
  if (treatmentType === 'FRACTIONAL_RESURFACING') {
    recommendations.push({
      category: 'Post-Treatment Care',
      priority: 'HIGH',
      recommendation: 'Fractional resurfacing requires dedicated downtime and aftercare',
      action: 'Ensure patient understands 5-10 day recovery period and strict sun avoidance'
    });
  }

  // Parameter-specific recommendations
  if (optimalParams.parameters.fluence?.value > 35) {
    recommendations.push({
      category: 'High Fluence',
      priority: 'MODERATE',
      recommendation: 'Fluence exceeds 35 J/cm² - monitor patient closely',
      action: 'Ensure cooling is optimal and check patient comfort frequently'
    });
  }

  recommendations.push({
    category: 'General Safety',
    priority: 'STANDARD',
    recommendation: 'Always perform test spot before full treatment',
    action: 'Wait 15-20 minutes to assess immediate response before proceeding'
  });

  return recommendations;
}

/**
 * Generates clinical approach and technique guidance
 */
function generateClinicalApproach(treatmentType, skinType, indication, patientAge, patientConcerns) {
  const approach = {
    overview: '',
    technique: [],
    expectedResults: '',
    patientCounseling: []
  };

  switch (treatmentType) {
    case 'BBL_PHOTOREJUVENATION':
      approach.overview = 'BBL photorejuvenation targets chromophores in the skin to improve pigmentation, vascular lesions, and overall skin quality.';
      approach.technique = [
        'Apply ultrasound gel evenly across treatment area',
        'Use overlapping passes with 10-20% overlap',
        'Treat entire area systematically to ensure uniform coverage',
        'Apply cooling between passes if needed',
        'Look for clinical endpoints: mild erythema for vascular, darkening of pigmentation'
      ];
      approach.expectedResults = 'Patients typically see gradual improvement over 3-4 sessions. Pigmentation will darken before flaking off. Vascular lesions will fade progressively.';
      break;

    case 'LASER_HAIR_REMOVAL':
      approach.overview = 'Laser hair removal targets melanin in hair follicles, requires treatment during active growth phase.';
      approach.technique = [
        'Ensure area is cleanly shaved 24 hours before treatment',
        'Apply cooling gel if using contact cooling',
        'Treat in systematic pattern to avoid missing areas',
        'Use perpendicular angle for optimal energy delivery',
        'Clinical endpoint: peri-follicular edema and erythema'
      ];
      approach.expectedResults = 'Hair reduction is gradual. Treated hairs will shed in 1-3 weeks. Requires 6-10 sessions for optimal results due to hair growth cycles.';
      break;

    case 'FRACTIONAL_RESURFACING':
      approach.overview = 'Fractional resurfacing creates controlled micro-injuries to stimulate collagen production and skin remodeling.';
      approach.technique = [
        'Apply topical anesthetic 30-45 minutes before treatment',
        'Treat in systematic pattern with appropriate density',
        'Multiple passes may be used, allowing skin to cool between passes',
        'Avoid overlapping passes excessively',
        'Clinical endpoint: pinpoint bleeding (for ablative) or immediate erythema'
      ];
      approach.expectedResults = 'Results develop over 3-6 months as collagen remodels. Initial downtime of 5-10 days. Best for texture, wrinkles, and scarring.';
      break;

    case 'VASCULAR_TREATMENT':
      approach.overview = 'Vascular laser treatment targets hemoglobin in blood vessels to coagulate and eliminate unwanted vasculature.';
      approach.technique = [
        'Clean and dry treatment area thoroughly',
        'Use cooling (cryogen or contact) to protect epidermis',
        'Trace visible vessels with appropriate spot size',
        'For larger vessels, use longer pulse widths',
        'Clinical endpoint: immediate darkening or disappearance of vessel'
      ];
      approach.expectedResults = 'Vessels typically fade over 2-4 weeks. Larger vessels may require multiple treatments. Avoid sun exposure during healing.';
      break;
  }

  approach.patientCounseling = [
    'Set realistic expectations about number of sessions required',
    'Emphasize importance of sun protection before and after treatment',
    'Discuss potential side effects: temporary redness, swelling, crusting',
    'Provide written aftercare instructions',
    'Schedule follow-up assessment 4-6 weeks post-treatment'
  ];

  if (skinType >= 4) {
    approach.patientCounseling.push(
      'Discuss increased risk of hyperpigmentation with darker skin types',
      'Stress importance of strict sun avoidance and sunscreen use'
    );
  }

  return approach;
}

/**
 * Generates pre and post treatment protocols
 */
function generateTreatmentProtocols(treatmentType, skinType, riskFactors) {
  const protocols = {
    preTreatment: [],
    duringTreatment: [],
    postTreatment: [],
    contraindications: []
  };

  // Universal pre-treatment protocols
  protocols.preTreatment = [
    'Obtain informed consent with treatment risks and benefits',
    'Take before photos in standardized lighting',
    'Clean treatment area thoroughly',
    'Perform test spot if first treatment',
    'Verify all parameters on device before starting'
  ];

  // Universal during-treatment protocols
  protocols.duringTreatment = [
    'Wear appropriate laser safety eyewear (provider and patient)',
    'Monitor patient comfort and adjust as needed',
    'Check skin response after each pass',
    'Document any adverse reactions immediately',
    'Maintain sterile technique throughout'
  ];

  // Universal post-treatment protocols
  protocols.postTreatment = [
    'Apply cooling (ice pack or cool compress) for 10-15 minutes',
    'Apply appropriate post-treatment product (aloe, hydrocortisone if needed)',
    'Provide written aftercare instructions',
    'Take after photos',
    'Schedule follow-up appointment'
  ];

  // Treatment-specific additions
  if (treatmentType === 'FRACTIONAL_RESURFACING') {
    protocols.preTreatment.push('Apply topical anesthetic 30-45 minutes before treatment');
    protocols.postTreatment.push(
      'Apply healing ointment (petrolatum-based)',
      'Instruct patient on gentle cleansing technique',
      'Prescribe prophylactic antiviral if indicated',
      'Emphasize no makeup for 24-48 hours'
    );
  }

  if (treatmentType === 'LASER_HAIR_REMOVAL') {
    protocols.preTreatment.push(
      'Ensure area is cleanly shaved (not waxed or plucked)',
      'Verify no recent tanning or sun exposure'
    );
  }

  // Risk factor specific protocols
  if (riskFactors.includes('RECENT_RETINOID_USE')) {
    protocols.preTreatment.push('Verify patient stopped retinoids 5-7 days before treatment');
  }

  if (skinType >= 4) {
    protocols.postTreatment.push(
      'Stress strict sun avoidance for 2 weeks',
      'Consider prophylactic hyperpigmentation treatment (hydroquinone, kojic acid)'
    );
  }

  // Universal contraindications
  protocols.contraindications = [
    'Active infection in treatment area',
    'History of keloid scarring (relative)',
    'Pregnancy (relative for most treatments)',
    'Recent Accutane use (within 6-12 months for resurfacing)',
    'Uncontrolled diabetes or immune disorders',
    'Active tan or sunburn',
    'Unrealistic patient expectations'
  ];

  return protocols;
}

/**
 * Generates PDF references for treatment guidance
 */
function generatePDFReferences(treatmentType) {
  const references = [
    {
      section: 'Safety Guidelines',
      page: null, // To be mapped from actual PDF
      description: 'General safety protocols and laser classification'
    },
    {
      section: 'Treatment Parameters',
      page: null,
      description: `Specific parameters for ${TREATMENT_MODALITIES[treatmentType]?.name}`
    },
    {
      section: 'Adverse Events',
      page: null,
      description: 'Recognition and management of complications'
    },
    {
      section: 'Maintenance',
      page: null,
      description: 'Device maintenance and calibration requirements'
    }
  ];

  return {
    document: 'Joule_Operator_Manual_Rev_Y.pdf',
    references,
    note: 'Refer to operator manual for complete device specifications and safety information'
  };
}

/**
 * Validates proposed treatment parameters
 */
function validateTreatmentParameters(params, treatmentType, skinType, riskFactors = []) {
  return validateParameters(params, treatmentType, skinType, riskFactors);
}

/**
 * Helper functions
 */
function generatePlanId() {
  return `LPOA-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

function getSkinTypeDescription(skinType) {
  const types = Object.values(SKIN_TYPES);
  return types.find(t => t.value === skinType)?.description || 'Unknown';
}

module.exports = {
  generateTreatmentPlan,
  validateTreatmentParameters,
  getOptimalParameters,
  TREATMENT_MODALITIES,
  TREATMENT_OUTCOMES,
  AREA_SIZES
};
