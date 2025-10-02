//
//  AnDisplayableEnum.swift
//  A360Scribe
//
//  Created by Mike Grankin on 22.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

// MARK: - Displayable Enum Protocol

protocol AnDisplayableEnum: AnDisplayable, CaseIterable {
  init?(displayTitle: String?)
}

extension AnDisplayableEnum {
  private static var displayTitleMap: [String: Self] {
    Dictionary(uniqueKeysWithValues: allCases.map { ($0.displayTitle, $0) })
  }

  init?(displayTitle: String?) {
    guard let displayTitle else { return nil }
    guard let match = Self.displayTitleMap[displayTitle] else { return nil }
    self = match
  }
}
