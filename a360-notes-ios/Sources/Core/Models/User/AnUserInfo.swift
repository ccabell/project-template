//
//  AnUserInfo.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

struct AnUserInfo: Codable {
  var password: String
  var lastLogin: Date
  var profile: AnUserProfile?
  var isBiometricAuthEnabled: Bool
  
  init(password: String, lastLogin: Date = Date(), profile: AnUserProfile? = nil, isBiometricAuthEnabled: Bool = false) {
    self.password = password
    self.lastLogin = lastLogin
    self.profile = profile
    self.isBiometricAuthEnabled = isBiometricAuthEnabled
  }
  
  mutating func update(password: String? = nil, lastLogin: Date? = nil, profile: AnUserProfile? = nil, isBiometricAuthEnabled: Bool? = nil) {
    if let password {
      self.password = password
    }
    if let lastLogin {
      self.lastLogin = lastLogin
    }
    if let profile {
      self.profile = profile
    }
    if let isBiometricAuthEnabled {
      self.isBiometricAuthEnabled = isBiometricAuthEnabled
    }
  }
  
  mutating func update(from other: AnUserInfo) {
    update(password: other.password, lastLogin: other.lastLogin, profile: other.profile, isBiometricAuthEnabled: other.isBiometricAuthEnabled)
  }
  
  mutating func toggleBiometricAuthEnabled() {
    self.isBiometricAuthEnabled = !self.isBiometricAuthEnabled
  }
}
