//
//  AnConsultationTab.swift
//  A360Scribe
//
//  Created by Mike Grankin on 21.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

enum AnConsultationTab: String, AnDisplayableEnum {
  case summaryAI
  case soapNotes
  case carePlan
  case email
  case questions
  case recording
  case intents
  case entities
  case sentiments
  
  var displayTitle: String {
    switch self {
    case .summaryAI: return "Summary"
    case .soapNotes: return "Clinical Notes"
    case .carePlan:  return "Care Plan"
    case .recording: return "Transcript"
    default:         return rawValue.capitalized
    }
  }
}
