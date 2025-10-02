/**
 * Laser Parameter Optimization Assistant (LPOA)
 * Safety Matrix and Parameter Configuration for Sciton Joule
 * 
 * This module defines safe operating ranges for laser parameters and their interdependencies.
 * All values should be validated against manufacturer specifications from the operator manual.
 */

// Fitzpatrick Skin Types
const SKIN_TYPES = {
  TYPE_I: { value: 1, description: 'Very fair, always burns, never tans', riskLevel: 'low' },
  TYPE_II: { value: 2, description: 'Fair, usually burns, tans minimally', riskLevel: 'low' },
  TYPE_III: { value: 3, description: 'Medium, sometimes burns, tans uniformly', riskLevel: 'moderate' },
  TYPE_IV: { value: 4, description: 'Olive, rarely burns, tans easily', riskLevel: 'moderate' },
  TYPE_V: { value: 5, description: 'Brown, very rarely burns, tans very easily', riskLevel: 'high' },
  TYPE_VI: { value: 6, description: 'Dark brown/black, never burns', riskLevel: 'high' }
};

// Treatment Modalities for Sciton Joule
const TREATMENT_MODALITIES = {
  BBL_PHOTOREJUVENATION: {
    name: 'BBL Photorejuvenation',
    wavelengths: [560, 590, 640, 'broadband'],
    indications: ['pigmentation', 'vascular', 'skin_rejuvenation'],
    defaultParams: {
      fluence: { min: 10, max: 40, unit: 'J/cm²', optimal: 25 },
      pulseWidth: { min: 3, max: 20, unit: 'ms', optimal: 10 },
      spotSize: { min: 10, max: 15, unit: 'mm', optimal: 15 },
      cooling: { type: 'contact', temperature: 5, unit: '°C' }
    }
  },
  LASER_HAIR_REMOVAL: {
    name: 'Laser Hair Removal',
    wavelengths: [755, 1064],
    indications: ['hair_removal'],
    defaultParams: {
      fluence: { min: 10, max: 50, unit: 'J/cm²', optimal: 30 },
      pulseWidth: { min: 10, max: 30, unit: 'ms', optimal: 20 },
      spotSize: { min: 12, max: 18, unit: 'mm', optimal: 15 },
      cooling: { type: 'contact', temperature: 5, unit: '°C' }
    }
  },
  FRACTIONAL_RESURFACING: {
    name: 'Fractional Resurfacing',
    wavelengths: [1470, 2940],
    indications: ['wrinkles', 'scars', 'texture', 'tightening'],
    defaultParams: {
      energy: { min: 10, max: 100, unit: 'mJ', optimal: 50 },
      density: { min: 5, max: 30, unit: '%', optimal: 20 },
      passes: { min: 1, max: 8, optimal: 4 },
      cooling: { type: 'air', enabled: true }
    }
  },
  VASCULAR_TREATMENT: {
    name: 'Vascular Treatment',
    wavelengths: [532, 1064],
    indications: ['telangiectasia', 'hemangioma', 'leg_veins', 'port_wine_stain'],
    defaultParams: {
      fluence: { min: 15, max: 60, unit: 'J/cm²', optimal: 35 },
      pulseWidth: { min: 0.5, max: 50, unit: 'ms', optimal: 10 },
      spotSize: { min: 3, max: 10, unit: 'mm', optimal: 6 },
      cooling: { type: 'cryogen_spray', enabled: true }
    }
  }
};

// Safety matrices per treatment and skin type
const SAFETY_MATRICES = {
  BBL_PHOTOREJUVENATION: {
    SKIN_TYPE_I_II: {
      fluence: { min: 15, max: 35, safe: 25, unit: 'J/cm²' },
      pulseWidth: { min: 5, max: 15, safe: 10, unit: 'ms' },
      spotSize: { min: 10, max: 15, safe: 15, unit: 'mm' }
    },
    SKIN_TYPE_III_IV: {
      fluence: { min: 12, max: 28, safe: 20, unit: 'J/cm²' },
      pulseWidth: { min: 8, max: 18, safe: 12, unit: 'ms' },
      spotSize: { min: 10, max: 15, safe: 15, unit: 'mm' }
    },
    SKIN_TYPE_V_VI: {
      fluence: { min: 10, max: 22, safe: 15, unit: 'J/cm²' },
      pulseWidth: { min: 10, max: 20, safe: 15, unit: 'ms' },
      spotSize: { min: 12, max: 15, safe: 15, unit: 'mm' }
    }
  },
  LASER_HAIR_REMOVAL: {
    SKIN_TYPE_I_II: {
      fluence: { min: 25, max: 50, safe: 40, unit: 'J/cm²' },
      pulseWidth: { min: 10, max: 30, safe: 20, unit: 'ms' },
      spotSize: { min: 12, max: 18, safe: 15, unit: 'mm' }
    },
    SKIN_TYPE_III_IV: {
      fluence: { min: 20, max: 40, safe: 30, unit: 'J/cm²' },
      pulseWidth: { min: 15, max: 30, safe: 25, unit: 'ms' },
      spotSize: { min: 12, max: 18, safe: 15, unit: 'mm' }
    },
    SKIN_TYPE_V_VI: {
      fluence: { min: 15, max: 30, safe: 22, unit: 'J/cm²' },
      pulseWidth: { min: 20, max: 40, safe: 30, unit: 'ms' },
      spotSize: { min: 15, max: 18, safe: 18, unit: 'mm' }
    }
  },
  FRACTIONAL_RESURFACING: {
    SKIN_TYPE_I_II: {
      energy: { min: 30, max: 100, safe: 70, unit: 'mJ' },
      density: { min: 15, max: 30, safe: 25, unit: '%' },
      passes: { min: 2, max: 8, safe: 4 }
    },
    SKIN_TYPE_III_IV: {
      energy: { min: 25, max: 80, safe: 55, unit: 'mJ' },
      density: { min: 10, max: 25, safe: 20, unit: '%' },
      passes: { min: 2, max: 6, safe: 3 }
    },
    SKIN_TYPE_V_VI: {
      energy: { min: 20, max: 60, safe: 40, unit: 'mJ' },
      density: { min: 5, max: 20, safe: 12, unit: '%' },
      passes: { min: 1, max: 4, safe: 2 }
    }
  },
  VASCULAR_TREATMENT: {
    SKIN_TYPE_I_II: {
      fluence: { min: 20, max: 60, safe: 40, unit: 'J/cm²' },
      pulseWidth: { min: 5, max: 40, safe: 20, unit: 'ms' },
      spotSize: { min: 3, max: 10, safe: 6, unit: 'mm' }
    },
    SKIN_TYPE_III_IV: {
      fluence: { min: 18, max: 50, safe: 35, unit: 'J/cm²' },
      pulseWidth: { min: 10, max: 50, safe: 30, unit: 'ms' },
      spotSize: { min: 4, max: 10, safe: 7, unit: 'mm' }
    },
    SKIN_TYPE_V_VI: {
      fluence: { min: 15, max: 40, safe: 25, unit: 'J/cm²' },
      pulseWidth: { min: 15, max: 50, safe: 35, unit: 'ms' },
      spotSize: { min: 5, max: 10, safe: 8, unit: 'mm' }
    }
  }
};

// Risk factors that modify treatment parameters
const RISK_FACTORS = {
  RECENT_SUN_EXPOSURE: { modifier: -0.2, description: 'Reduce fluence by 20%' },
  TAN_SKIN: { modifier: -0.15, description: 'Reduce fluence by 15%' },
  SENSITIVE_SKIN: { modifier: -0.15, description: 'Reduce fluence by 15%' },
  PREVIOUS_TREATMENT: { modifier: 0.1, description: 'Can increase by 10% if tolerated' },
  THIN_SKIN: { modifier: -0.1, description: 'Reduce fluence by 10%' },
  ACTIVE_ACNE: { modifier: -0.2, description: 'Reduce fluence by 20%, avoid affected areas' },
  RECENT_RETINOID_USE: { modifier: -0.15, description: 'Reduce fluence by 15%' }
};

// Parameter interdependencies and validation rules
const PARAMETER_RULES = {
  // Higher fluence requires shorter pulse width for safety
  FLUENCE_PULSE_INVERSE: {
    rule: (fluence, pulseWidth, skinType) => {
      if (skinType > 3 && fluence > 30 && pulseWidth < 15) {
        return {
          valid: false,
          warning: 'High fluence with short pulse on darker skin increases risk of thermal damage',
          recommendation: 'Increase pulse width to at least 15ms or reduce fluence'
        };
      }
      return { valid: true };
    }
  },
  
  // Larger spot sizes allow for slightly higher fluence
  SPOT_SIZE_FLUENCE_RELATION: {
    rule: (spotSize, fluence, maxFluence) => {
      const adjustedMax = maxFluence + (spotSize > 12 ? 5 : 0);
      if (fluence > adjustedMax) {
        return {
          valid: false,
          warning: 'Fluence exceeds safe limits for spot size',
          recommendation: `Reduce fluence to ${adjustedMax} J/cm² or less`
        };
      }
      return { valid: true };
    }
  },
  
  // Cooling is mandatory for high fluence treatments
  COOLING_REQUIREMENT: {
    rule: (fluence, coolingEnabled) => {
      if (fluence > 35 && !coolingEnabled) {
        return {
          valid: false,
          warning: 'Cooling must be enabled for fluence above 35 J/cm²',
          recommendation: 'Enable cooling system before proceeding'
        };
      }
      return { valid: true };
    }
  },
  
  // Multiple passes require reduced energy per pass
  PASSES_ENERGY_INVERSE: {
    rule: (passes, energy, safeEnergy) => {
      if (passes > 4) {
        const adjustedSafe = safeEnergy * (4 / passes);
        if (energy > adjustedSafe) {
          return {
            valid: false,
            warning: 'Energy per pass is too high for multiple passes',
            recommendation: `Reduce energy to ${adjustedSafe.toFixed(1)} mJ or reduce number of passes`
          };
        }
      }
      return { valid: true };
    }
  }
};

/**
 * Validates laser parameters against safety matrix
 * @param {Object} params - Treatment parameters
 * @param {string} treatmentType - Type of treatment
 * @param {number} skinType - Fitzpatrick skin type (1-6)
 * @param {Array} riskFactors - Array of applicable risk factors
 * @returns {Object} Validation result with warnings and recommendations
 */
function validateParameters(params, treatmentType, skinType, riskFactors = []) {
  const skinTypeKey = getSkinTypeKey(skinType);
  const safetyMatrix = SAFETY_MATRICES[treatmentType]?.[skinTypeKey];
  
  if (!safetyMatrix) {
    return {
      valid: false,
      error: 'Invalid treatment type or skin type',
      warnings: [],
      recommendations: []
    };
  }
  
  const warnings = [];
  const recommendations = [];
  let isValid = true;
  
  // Apply risk factor modifiers
  let adjustedParams = { ...params };
  let totalModifier = 1.0;
  
  riskFactors.forEach(factor => {
    if (RISK_FACTORS[factor]) {
      totalModifier += RISK_FACTORS[factor].modifier;
      recommendations.push(RISK_FACTORS[factor].description);
    }
  });
  
  // Validate each parameter against safety ranges
  Object.keys(safetyMatrix).forEach(paramKey => {
    const paramValue = adjustedParams[paramKey];
    const safeRange = safetyMatrix[paramKey];
    
    if (paramValue !== undefined) {
      // Apply modifier for fluence/energy
      let adjustedValue = paramValue;
      if (paramKey === 'fluence' || paramKey === 'energy') {
        adjustedValue = paramValue * totalModifier;
      }
      
      if (adjustedValue < safeRange.min) {
        warnings.push(`${paramKey} (${adjustedValue.toFixed(1)} ${safeRange.unit}) is below minimum safe value (${safeRange.min} ${safeRange.unit})`);
        recommendations.push(`Increase ${paramKey} to at least ${safeRange.min} ${safeRange.unit} for efficacy`);
      }
      
      if (adjustedValue > safeRange.max) {
        isValid = false;
        warnings.push(`${paramKey} (${adjustedValue.toFixed(1)} ${safeRange.unit}) exceeds maximum safe value (${safeRange.max} ${safeRange.unit})`);
        recommendations.push(`CRITICAL: Reduce ${paramKey} to ${safeRange.safe} ${safeRange.unit} or less`);
      }
      
      if (adjustedValue > safeRange.safe && adjustedValue <= safeRange.max) {
        warnings.push(`${paramKey} is above optimal safe value. Monitor patient closely.`);
      }
    }
  });
  
  // Apply interdependency rules
  Object.values(PARAMETER_RULES).forEach(({ rule }) => {
    const result = rule(
      adjustedParams.fluence,
      adjustedParams.pulseWidth,
      skinType,
      adjustedParams.spotSize,
      adjustedParams.cooling,
      adjustedParams.passes,
      adjustedParams.energy,
      safetyMatrix.fluence?.safe || safetyMatrix.energy?.safe
    );
    
    if (!result.valid) {
      isValid = false;
      warnings.push(result.warning);
      recommendations.push(result.recommendation);
    }
  });
  
  return {
    valid: isValid,
    warnings,
    recommendations,
    adjustedParams,
    safetyMatrix,
    riskLevel: getRiskLevel(warnings.length, isValid)
  };
}

/**
 * Gets optimal parameters for a treatment
 * @param {string} treatmentType - Type of treatment
 * @param {number} skinType - Fitzpatrick skin type
 * @param {Array} riskFactors - Risk factors to consider
 * @returns {Object} Optimal parameters with safety ranges
 */
function getOptimalParameters(treatmentType, skinType, riskFactors = []) {
  const skinTypeKey = getSkinTypeKey(skinType);
  const safetyMatrix = SAFETY_MATRICES[treatmentType]?.[skinTypeKey];
  const treatment = TREATMENT_MODALITIES[treatmentType];
  
  if (!safetyMatrix || !treatment) {
    return null;
  }
  
  // Start with safe values
  const optimalParams = {};
  Object.keys(safetyMatrix).forEach(key => {
    optimalParams[key] = {
      value: safetyMatrix[key].safe,
      min: safetyMatrix[key].min,
      max: safetyMatrix[key].max,
      unit: safetyMatrix[key].unit
    };
  });
  
  // Adjust for risk factors
  let modifier = 1.0;
  const appliedFactors = [];
  
  riskFactors.forEach(factor => {
    if (RISK_FACTORS[factor]) {
      modifier += RISK_FACTORS[factor].modifier;
      appliedFactors.push({
        factor,
        description: RISK_FACTORS[factor].description
      });
    }
  });
  
  // Apply modifier to fluence/energy
  if (optimalParams.fluence) {
    optimalParams.fluence.value = Math.round(optimalParams.fluence.value * modifier * 10) / 10;
  }
  if (optimalParams.energy) {
    optimalParams.energy.value = Math.round(optimalParams.energy.value * modifier * 10) / 10;
  }
  
  return {
    treatment: treatment.name,
    skinType,
    parameters: optimalParams,
    appliedModifiers: appliedFactors,
    wavelengths: treatment.wavelengths,
    cooling: treatment.defaultParams.cooling
  };
}

function getSkinTypeKey(skinType) {
  if (skinType <= 2) return 'SKIN_TYPE_I_II';
  if (skinType <= 4) return 'SKIN_TYPE_III_IV';
  return 'SKIN_TYPE_V_VI';
}

function getRiskLevel(warningCount, isValid) {
  if (!isValid) return 'CRITICAL';
  if (warningCount > 2) return 'HIGH';
  if (warningCount > 0) return 'MODERATE';
  return 'LOW';
}

module.exports = {
  SKIN_TYPES,
  TREATMENT_MODALITIES,
  SAFETY_MATRICES,
  RISK_FACTORS,
  PARAMETER_RULES,
  validateParameters,
  getOptimalParameters
};
