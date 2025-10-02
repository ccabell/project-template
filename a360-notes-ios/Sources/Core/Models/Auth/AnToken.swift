//
//  AnToken.swift
//  A360Scribe
//
//  Created by Mike Grankin on 02.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

struct AnToken: Codable {
  let tokenType: String
  let accessToken: String
  let idToken: String
  let refreshToken: String?
  let expiresIn: Int
  let creationDate: Date = Date()
  
  enum CodingKeys: String, CodingKey {
    case tokenType = "token_type"
    case accessToken = "access_token"
    case idToken = "id_token"
    case refreshToken = "refresh_token"
    case expiresIn = "expires_in"
  }
  
  var isExpired: Bool {
    return Date() > creationDate.addingTimeInterval(TimeInterval(expiresIn))
  }
  
  var authHttpHeaderValue: String {
    return "\(tokenType) \(accessToken)"
  }
}
