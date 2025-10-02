//
//  AnError.swift
//  A360Scribe
//
//  Created by Mike Grankin on 27.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

struct AnError: LocalizedError {
  
  // MARK: - Public Properties
  
  let text: String
  let statusCode: Int?
  var errorDescription: String? { text }
  
  // MARK: - Constants
  
  private static let unknownStatusCode = -1
  
  // MARK: - Lifecycle
  
  init(_ detail: Any, statusCode: Int = Self.unknownStatusCode) {
    text = AnError.parse(detail: detail)
    self.statusCode = statusCode
  }
  
  // MARK: - Private Functions
  
  private static func parse(detail: Any) -> String {
    if let string = detail as? String { return string }
    if let array = detail as? [Any] {
      return array.map { parse(detail: $0) }.joined(separator: "\n")
    }
    if let dict = detail as? [String: Any] {
      return dict.map { key, value in "\(key) \(parse(detail: value))" }.joined(separator: "\n")
    }
    return "\(detail)"
  }
}
