//
//  AnUser+Shortcuts.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

extension AnUser {
  /// Shorthand for `info.password`
  var password: String {
    return info.password
  }
  
  /// Shorthand for `info.lastLogin`
  var lastLogin: Date {
    return info.lastLogin
  }
  
  /// Shorthand for `info.isBiometricAuthEnabled`
  var isBiometricAuthEnabled: Bool {
    return info.isBiometricAuthEnabled
  }
  
  /// Shorthand for `info.profile`
  var profile: AnUserProfile? {
    return info.profile
  }
  
  /// Shorthand for the expert’s id (`info.profile?.expert?.id`)
  var expertId: String? {
    return info.profile?.expert?.id
  }
  
  /// Shorthand for `info.profile?.expert?.practice?.id`
  var practiceId: String? {
    guard let practice = info.profile?.expert?.practice else { return nil }
    return practice.id
  }

  /// Shorthand for `info.profile?.expert?.practice?.accountType`
  var practiceAccountType: AnPracticeAccountType? {
    return info.profile?.expert?.practice?.accountType
  }

  /// Shorthand for `info.profile?.expert?.role?.hasPractice`
  var hasPractice: Bool? {
    return info.profile?.expert?.role?.hasPractice
  }

  /// Shorthand for `info.profile?.expert?.practice?.accountType.hideTranscript`
  var hideTranscript: Bool? {
    return info.profile?.expert?.practice?.accountType?.hideTranscript
  }

  /// Shorthand for `info.profile?.expert?.role`
  var role: AnUserRole? {
    return info.profile?.expert?.role
  }
}
