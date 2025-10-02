//
//  AnPatient.swift
//  A360Scribe
//
//  Created by Mike Grankin on 04.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

struct AnPatient: Codable {
  let id: String
  var firstName: String
  var middleName: String?
  var lastName: String
  var birthDate: String
  var title: AnPersonTitle?
  var genderIdentity: AnGenderIdentity?
  var ethnicity: AnEthnicity?
  var occupation: String?
  var phone: String?
  var email: String?
  var summary: String?
  var lastConsultation: Date?
  var isActive: Bool?
  
  enum CodingKeys: String, CodingKey {
    case id
    case firstName = "first_name"
    case middleName = "middle_name"
    case lastName = "last_name"
    case birthDate = "birth_date"
    case title
    case genderIdentity = "gender_identity"
    case ethnicity
    case occupation
    case phone
    case email
    case summary = "patient_summary"
    case lastConsultation = "last_consultation_datetime"
    case isActive = "is_active"
  }
  
  var displayName: String {
    return "\(lastName), \(firstName)"
  }
  
  var formattedBirthDateWithAge: String? {
    return AnDateFormatter.shared.convert(dateString: birthDate, from: .serverDate, to: .shortAmericanDate)
  }
  
  var formattedLastConsultationDate: String? {
    guard let lastConsultation else { return nil }
    return AnDateFormatter.shared.convert(date: lastConsultation, to: .americanDate)
  }
  
}
