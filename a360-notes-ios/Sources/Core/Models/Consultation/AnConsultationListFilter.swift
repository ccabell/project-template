//
//  AnConsultationListFilter.swift
//  A360Scribe
//
//  Created by Mike Grankin on 13.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

struct AnConsultationListFilter {
  var orderBy: AnConsultationListFilter.OrderBy = .lastConsultationLatestFirst
  var statuses: [AnConsultationStatus] = []
  var expert: AnExpert?
  var workflow: AnWorkflow?

  var isFilterEmpty: Bool {
    return orderBy == .lastConsultationLatestFirst && statuses.isEmpty && expert == nil && workflow == nil
  }
  
  var parameters: [String: Any] {
    var params = orderBy.parameters
    if !statuses.isEmpty {
      params["consultation_status"] = statuses.map { $0.rawValue }
    }
    if let expert {
      params["expert_id"] = expert.id
    }
    if let workflow {
      params["workflow_id"] = workflow.id
    }
    return params
  }
  
  enum OrderBy: AnDisplayableEnum {
    case lastConsultationEarliestFirst
    case lastConsultationLatestFirst

    var displayTitle: String {
      switch self {
      case .lastConsultationEarliestFirst:
        return "Earliest to latest"
      case .lastConsultationLatestFirst:
        return "Latest to earliest"
      }
    }
    
    var groupTitle: String? {
      switch self {
      case .lastConsultationEarliestFirst, .lastConsultationLatestFirst:
        return "Last Consultation Date"
      }
    }
    
    var parameters: [String: Any] {
      switch self {
      case .lastConsultationEarliestFirst:
        return ["order": ["started_at,asc"]]
      case .lastConsultationLatestFirst:
        return ["order": ["started_at,desc"]]
      }
    }
  }
}
