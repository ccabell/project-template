//
//  AnExpert.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnExpert: Codable, AnDisplayable {
  let id: String
  let userId: String?
  let title: String?
  let firstName: String
  let middleName: String?
  let lastName: String
  let email: String?
  let phone: String?
  let role: AnUserRole?
  let position: String?
  let practice: AnPractice?
  let createdAt: String?
  let updatedAt: String?
  let isActive: Bool?
  
  enum CodingKeys: String, CodingKey {
    case id
    case userId = "user_id"
    case title
    case firstName = "first_name"
    case middleName = "middle_name"
    case lastName = "last_name"
    case email
    case phone
    case role
    case position
    case practice
    case createdAt = "created_at"
    case updatedAt = "updated_at"
    case isActive = "is_active"
  }
  
  var displayTitle: String {
    return "\(firstName) \(lastName)"
  }
}

struct AnExpertResponse: Codable, AnPaginatedResponseProtocol {
  let total: Int
  let page: Int
  let size: Int
  let items: [AnExpert]
}

struct AnPractice: Codable, Equatable {
  let id: String
  let name: String
  let accountType: AnPracticeAccountType?
  
  enum CodingKeys: String, CodingKey {
    case id
    case name
    case accountType = "account_type"
  }
}

enum AnPracticeAccountType: Int, Codable {
  case live = 1
  case demo = 2
  case test = 3
  case beta = 4
  
  var hideTranscript: Bool {
    return [.live, .beta].contains(self)
  }
}
