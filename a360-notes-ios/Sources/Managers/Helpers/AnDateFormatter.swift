//
//  AnDateFormatter.swift
//  A360Scribe
//
//  Created by Mike Grankin on 15.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

final class AnDateFormatter {
  
  // MARK: - Public Properties
  
  static let shared = AnDateFormatter()
  
  // MARK: - Enum
  
  enum Format {
    case serverDate
    case serverDateTime
    case americanDate
    case shortAmericanDate
    case shortAmericanDateTime
    case americanTime
    
    var format: String {
      switch self {
      case .serverDate:
        return "yyyy-MM-dd"
      case .serverDateTime:
        return "yyyy-MM-dd'T'HH:mm:ss.SSSXXXXX"
      case .americanDate:
        return "MM/dd/yyyy"
      case .shortAmericanDate:
        return "M/d/yyyy"
      case .shortAmericanDateTime:
        return "M/d/yyyy h:mm a"
      case .americanTime:
        return "h:mm a"
      }
    }
  }
  
  // MARK: - Public Functions
  
  func isValidBirthdate(dateString: String?) -> Bool {
    guard let dateString,
          dateString.count == 10,
          let birthDate = formatter(for: .americanDate).date(from: dateString),
          let minDate = Calendar.current.date(from: DateComponents(year: 1900, month: 1, day: 1)),
          (minDate...Date()).contains(birthDate)
    else {
      return false
    }
    return true
  }
  
  func convert(dateString: String?, from fromFormat: Format, to toFormat: Format) -> String? {
    guard let dateString,
          let date = formatter(for: fromFormat).date(from: dateString) else {
      return nil
    }
    
    let formatted = formatter(for: toFormat).string(from: date)
    
    if toFormat == .shortAmericanDate,
       let age = calculateAge(from: date) {
      return "\(formatted) (\(age))"
    }
    
    return formatted
  }
  
  func convert(dateString: String?, from fromFormat: Format) -> Date? {
    guard let dateString else { return nil }
    return formatter(for: fromFormat).date(from: dateString)
  }
  
  func convert(date: Date, to toFormat: Format) -> String {
    let formatter = formatter(for: toFormat)
    return formatter.string(from: date)
  }
  
  // MARK: - Private Functions
  
  private func formatter(for format: Format) -> DateFormatter {
    let formatter = DateFormatter()
    formatter.dateFormat = format.format
    formatter.locale = Locale(identifier: "en_US_POSIX")
    return formatter
  }
  
  private func calculateAge(from date: Date) -> Int? {
    Calendar.current.dateComponents([.year], from: date, to: Date()).year
  }
}
