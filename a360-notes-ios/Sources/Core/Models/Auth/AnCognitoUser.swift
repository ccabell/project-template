//
//  AnCognitoUser.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnCognitoUser: Codable {
  let username: String
  let email: String
  let isActive: Bool
  
  enum CodingKeys: String, CodingKey {
    case username
    case email
    case isActive = "is_active"
  }
}
