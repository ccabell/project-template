//
//  AnWebViewProvider.swift
//  A360Scribe
//
//  Created by Mike Grankin on 16.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

enum AnWebViewProvider {
  case consultationSession(patientId: String, consultationId: String, activeTab: String, resumingConsultation: Bool)
  case consultationProfile(patientId: String, consultationId: String)
  
  var path: String {
    switch self {
    case .consultationSession(let patientId, let consultationId, _, _):
      return "/patients/\(patientId)/consultation-session/\(consultationId)"
    case .consultationProfile(let patientId, let consultationId):
      return "/patients/\(patientId)/consultations/\(consultationId)/consultation-summary"
    }
  }
  
  var queryItems: [URLQueryItem] {
    switch self {
    case .consultationSession(_, _, let activeTab, let resumingConsultation):
      return [.init(name: "activeTab", value: activeTab),
              .init(name: "isResumeConsultation", value: "\(resumingConsultation)")]
    case .consultationProfile:
      return []
    }
  }
}
