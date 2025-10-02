//
//  AnPatientParams.swift
//  A360Scribe
//
//  Created by Mike Grankin on 30.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnPatientParams {
  var id: String?
  var firstName: String
  var lastName: String
  var birthDate: String
  var middleName: String?
  var title: AnPersonTitle?
  var genderIdentity: AnGenderIdentity?
  var ethnicity: AnEthnicity?
  var occupation: String?
  var phone: String?
  var email: String?
  var summary: String?
  var allowDuplicate: Bool = false
  
  // MARK: - Request Payload
  
  var forRequest: [String: Any?] {
    guard let serverBirthDate = AnDateFormatter.shared.convert(dateString: birthDate, from: .americanDate, to: .serverDate) else {
      fatalError("Unable to convert birthDate to server format")
    }
    
    var payload: [String: Any?] = ["first_name": firstName, "last_name": lastName, "birth_date": serverBirthDate]
    
    if id == nil {
      payload["expert_id"] = AnUserManager.shared.currentUser?.expertId as Any
      payload["practice_id"] = AnUserManager.shared.currentUser?.practiceId as Any
    } else {
      payload["gender_identity"] = genderIdentity?.rawValue as Any?
      payload["ethnicity"] = ethnicity?.rawValue as Any?
      payload["occupation"] = occupation as Any?
      payload["patient_summary"] = summary as Any?
    }
    
    payload["middle_name"] = middleName as Any?
    payload["title"] = title?.rawValue as Any?
    payload["phone"] = phone as Any?
    payload["email"] = email as Any?
    if allowDuplicate { payload["allow_duplicate"] = true }
    return payload
  }
}

struct AnPatientSummaryParams {
  var id: String
  var summary: String
  
  // MARK: - Request Payload
  
  var forRequest: [String: Any] {
    let payload: [String: Any] = ["patient_summary": summary]
    return payload
  }
}
