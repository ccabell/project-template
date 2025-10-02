//
//  AnUser.swift
//  A360Scribe
//
//  Created by Mike Grankin on 07.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

struct AnUser: Codable {
  let username: String
  var serverEnvironment: AnServerEnvironment
  var info: AnUserInfo
  
  var displayName: String {
    let last = profile?.expert?.lastName ?? ""
    let first = profile?.expert?.firstName ?? ""
    if !last.isEmpty, !first.isEmpty {
      return "\(last), \(first)"
    } else if !last.isEmpty {
      return last
    } else if !first.isEmpty {
      return first
    }
    return profile?.cognitoUser.username ?? username
  }
  
  var nameForInitials: String { return profile?.cognitoUser.username ?? "" }
  var avatarColor: UIColor { return (profile?.cognitoUser.username ?? "").avatarColor }
  
  // MARK: - Initialization
  
  init(username: String, password: String, profile: AnUserProfile?) {
    self.username = username
    self.serverEnvironment = GlobalLinks.serverEnvironment
    self.info = AnUserInfo(password: password,
                           lastLogin: Date(),
                           profile: profile,
                           isBiometricAuthEnabled: false)
  }
  
  // MARK: - Legacy methods for migrate stored users
  
  private enum CodingKeys: String, CodingKey {
    case username
    case serverEnvironment
    case info
    // legacy flat keys for decoding only
    case password
    case lastLogin
    case profile
    case isBiometricAuthEnabled
  }
  
  init(from decoder: Decoder) throws {
    let container = try decoder.container(keyedBy: CodingKeys.self)
    username = try container.decode(String.self, forKey: .username)
    serverEnvironment = try container.decode(AnServerEnvironment.self, forKey: .serverEnvironment)
    if let nested = try? container.decode(AnUserInfo.self, forKey: .info) {
      info = nested
    } else {
      // fallback to legacy flat props
      let password = try container.decode(String.self, forKey: .password)
      let lastLogin = try container.decode(Date.self, forKey: .lastLogin)
      let profile = try container.decodeIfPresent(AnUserProfile.self, forKey: .profile)
      let bioFlag: Bool = try container.decodeIfPresent(Bool.self, forKey: .isBiometricAuthEnabled) ?? false
      info = AnUserInfo(password: password, lastLogin: lastLogin, profile: profile, isBiometricAuthEnabled: bioFlag)
    }
  }
  
  func encode(to encoder: Encoder) throws {
    var container = encoder.container(keyedBy: CodingKeys.self)
    try container.encode(username, forKey: .username)
    try container.encode(serverEnvironment, forKey: .serverEnvironment)
    try container.encode(info, forKey: .info)
  }
}
