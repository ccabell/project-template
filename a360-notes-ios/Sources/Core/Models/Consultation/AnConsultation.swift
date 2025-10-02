//
//  AnConsultation.swift
//  A360Scribe
//
//  Created by Mike Grankin on 04.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

struct AnConsultation: Codable {
  let id: String
  let expert: AnExpert
  let patient: AnPatient
  let status: AnConsultationStatus
  let startedAt: Date?
  let finishedAt: Date?
  let workflow: AnWorkflow?
  
  enum CodingKeys: String, CodingKey {
    case id
    case expert
    case patient
    case status = "consultation_status"
    case startedAt = "started_at"
    case finishedAt = "finished_at"
    case workflow
  }
  
  var prohibitedActionMessage: ProhibitedActionMessage? {
    if status != .idle {
      return .notIdle
    }
    if expert.id != AnUserManager.shared.currentUser?.expertId {
      return .anotherExpert
    }
    
    return nil
  }
  
  enum ProhibitedActionMessage: String {
    case notIdle = "You can only perform this action with consultations that in IDLE status."
    case anotherExpert = "You can only perform this action with consultations that you created."
  }
}

enum AnConsultationStatus: Int, Codable, AnDisplayableEnum {
  case onGoing = 1
  case idle = 2
  case finished = 3
  
  var displayTitle: String {
    switch self {
    case .onGoing:
      return "On-Going"
    case .idle:
      return "Idle"
    case .finished:
      return "Finished"
    }
  }
  
  var foregroundColor: UIColor {
    switch self {
    case .onGoing:
      return .primarySoft
    case .idle:
      return .textSecondary
    case .finished:
      return .successMedium
    }
  }
  
  var backgroundColor: UIColor {
    switch self {
    case .onGoing:
      return .infoBackground
    case .idle:
      return .surfaceSoft
    case .finished:
      return .successSoft
    }
  }
}
