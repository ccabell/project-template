//
//  AnPatientListFilter.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

struct AnPatientListFilter {
  var orderBy: AnPatientListFilter.OrderBy = .nameAToZ
  var ageFrom: Int?
  var ageTo: Int?
  var lastConsultationFrom: Date?
  var lastConsultationTo: Date?
  var status: AnPatientStatus = .active
  
  var isFilterEmpty: Bool {
    return orderBy == .nameAToZ && ageFrom == nil && ageTo == nil && lastConsultationFrom == nil && lastConsultationTo == nil && status == .active
  }
  
  var parameters: [String: Any] {
    var params = orderBy.parameters
    if let ageFrom {
      params["min_age"] = String(ageFrom)
    }
    if let ageTo {
      params["max_age"] = String(ageTo)
    }
    if var lastConsultationFrom {
      lastConsultationFrom = Calendar.current.startOfDay(for: lastConsultationFrom)
      params["last_consultation_from"] = AnDateFormatter.shared.convert(date: lastConsultationFrom, to: .serverDateTime)
    }
    if var lastConsultationTo {
      lastConsultationTo = Calendar.current.date(bySettingHour: 23, minute: 59, second: 59, of: lastConsultationTo) ?? lastConsultationTo
      params["last_consultation_to"] = AnDateFormatter.shared.convert(date: lastConsultationTo, to: .serverDateTime)
    }
    if status != .all {
      params["is_active"] = status == .active
    }
    return params
  }
  
  enum OrderBy: AnDisplayableEnum {
    case nameAToZ
    case nameZToA
    case lastConsultationEarliestFirst
    case lastConsultationLatestFirst

    var displayTitle: String {
      switch self {
      case .nameAToZ:
        return "A to Z"
      case .nameZToA:
        return "Z to A"
      case .lastConsultationEarliestFirst:
        return "Earliest to latest"
      case .lastConsultationLatestFirst:
        return "Latest to earliest"
      }
    }
    
    var groupTitle: String? {
      switch self {
      case .nameAToZ, .nameZToA:
        return "Name"
      case .lastConsultationEarliestFirst, .lastConsultationLatestFirst:
        return "Last Consultation Date"
      }
    }
    
    var parameters: [String: Any] {
      switch self {
      case .nameAToZ:
        return ["order": ["last_name,asc", "first_name,asc"]]
      case .nameZToA:
        return ["order": ["last_name,desc", "first_name,desc"]]
      case .lastConsultationEarliestFirst:
        return ["order": ["last_consultation_datetime,asc"]]
      case .lastConsultationLatestFirst:
        return ["order": ["last_consultation_datetime,desc"]]
      }
    }
  }
}
