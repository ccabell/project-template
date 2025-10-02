//
//  AnPatientEnums.swift
//  A360Scribe
//
//  Created by Mike Grankin on 22.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

// MARK: - Person Title

enum AnPersonTitle: String, Codable, AnDisplayableEnum {
  case mr
  case mrs
  case ms
  case miss
  case dr
  case prof
  case rev
  case hon
  case phd

  var displayTitle: String {
    switch self {
    case .mr:   return "Mr."
    case .mrs:  return "Mrs."
    case .ms:   return "Ms."
    case .miss: return "Miss"
    case .dr:   return "Dr."
    case .prof: return "Prof."
    case .rev:  return "Rev."
    case .hon:  return "Hon."
    case .phd:  return "PhD"
    }
  }
}

// MARK: - Gender Identity

enum AnGenderIdentity: String, Codable, AnDisplayableEnum {
  case male = "male"
  case female = "female"
  case nonBinary = "non_binary"
  case preferToSelfDescribe = "prefer_to_self_describe"
  case preferNotToSay = "prefer_not_to_say"

  var displayTitle: String {
    switch self {
    case .male:                 return "Male"
    case .female:               return "Female"
    case .nonBinary:            return "Non-binary"
    case .preferToSelfDescribe: return "Prefer to self-describe"
    case .preferNotToSay:       return "Prefer not to say"
    }
  }
}

// MARK: - Ethnicity

enum AnEthnicity: String, Codable, AnDisplayableEnum {
  case white = "white"
  case blackOrAfricanAmerican = "black_or_african_american"
  case americanIndianOrAlaskaNative = "american_indian_or_alaska_native"
  case asian = "asian"
  case nativeHawaiianOrOtherPacificIslander = "native_hawaiian_or_other_pacific_islander"
  case hispanicOrLatino = "hispanic_or_latino"
  case middleEasternOrNorthAfrican = "middle_eastern_or_north_african"
  case other = "other"
  case preferNotToSay = "prefer_not_to_say"

  var displayTitle: String {
    switch self {
    case .white:                           return "White"
    case .blackOrAfricanAmerican:          return "Black or African American"
    case .americanIndianOrAlaskaNative:    return "American Indian or Alaska Native"
    case .asian:                           return "Asian"
    case .nativeHawaiianOrOtherPacificIslander: return "Native Hawaiian or Other Pacific Islander"
    case .hispanicOrLatino:                return "Hispanic or Latino"
    case .middleEasternOrNorthAfrican:     return "Middle Eastern or North African"
    case .other:                           return "Other"
    case .preferNotToSay:                  return "Prefer Not to Say"
    }
  }
}

// MARK: - Status

enum AnPatientStatus: AnDisplayableEnum {
  case all
  case active
  case inactive

  var displayTitle: String {
    switch self {
    case .all:      return "All"
    case .active:   return "Active"
    case .inactive: return "Inactive"
    }
  }
}
