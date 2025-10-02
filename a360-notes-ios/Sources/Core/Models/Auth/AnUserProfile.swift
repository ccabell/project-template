//
//  AnUserProfile.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnUserProfile: Codable {
  let cognitoUser: AnCognitoUser
  let expert: AnExpert?
  
  enum CodingKeys: String, CodingKey {
    case cognitoUser = "cognito_user"
    case expert
  }
}
