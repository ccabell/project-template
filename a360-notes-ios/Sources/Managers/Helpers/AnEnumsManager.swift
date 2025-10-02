//
//  AnEnumsManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 22.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

// MARK: - Enums Models

public enum AnEnumType: String, CaseIterable {
  case bloodTypes = "blood_types"
  case painTolerances = "pain_tolerances"
  case alcoholConsumption = "alcohol_consumption"
  case attachmentTypes = "attachment_types"
  case biologicalSexes = "biological_sexes"
  case practiceStatuses = "practice_statuses"
  case genders = "genders"
  case consultationStatus = "consultation_status"
  case smoking = "smoking"
  case personTitles = "person_titles"
  case ethnicities = "ethnicities"
}

public struct AnEnumValue: Decodable {
  public let name: String
  public let value: String
  
  public init(from decoder: Decoder) throws {
    let container = try decoder.container(keyedBy: CodingKeys.self)
    name = try container.decode(String.self, forKey: .name)
    if let stringValue = try? container.decode(String.self, forKey: .value) {
      value = stringValue
    } else if let intValue = try? container.decode(Int.self, forKey: .value) {
      value = String(intValue)
    } else {
      let context = DecodingError.Context(codingPath: [CodingKeys.value], debugDescription: "Expected String or Int for value")
      throw DecodingError.typeMismatch(String.self, context)
    }
  }
  
  private enum CodingKeys: String, CodingKey { case name, value }
}

public typealias AnAllEnumsResponse = [String: [AnEnumValue]]

// MARK: - Manager

final class AnEnumsManager {
  
  // MARK: - Public Properties
  
  public static let shared = AnEnumsManager()
  
  // MARK: - Private Properties
  
  private var cache: [AnEnumType: [AnEnumValue]]?
  private lazy var practiceService: AnPracticeService = AnAPIService()
  
  // MARK: - Public Functions
  
  public func values(for type: AnEnumType) async throws -> [AnEnumValue] {
    if let existing = cache?[type] { return existing }
    try await loadAllEnumsIfNeeded()
    return cache?[type] ?? []
  }
  
  public func clearAllEnums() { cache = nil }
  
  // MARK: - Private Functions
  
  private func loadAllEnumsIfNeeded() async throws {
    guard cache == nil else { return }
    let raw: AnAllEnumsResponse = try await practiceService.fetchAllEnums()
    var mapped: [AnEnumType: [AnEnumValue]] = [:]
    for (key, items) in raw {
      guard let type = AnEnumType(rawValue: key) else { continue }
      mapped[type] = items
    }
    cache = mapped
  }
}
