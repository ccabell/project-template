//
//  AnUserRole.swift
//  A360Scribe
//
//  Created by Mike Grankin on 16.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

enum AnUserRole: String, Codable {
  case admin = "ROLE_ADMIN"
  case aiTester = "ROLE_AI_TESTER"
  case practiceAdmin = "ROLE_PRACTICE_ADMIN"
  case practiceDoctor = "ROLE_PRACTICE_DOCTOR"
  
  var hasPractice: Bool {
    return [.practiceAdmin, .practiceDoctor].contains(self)
  }
}
