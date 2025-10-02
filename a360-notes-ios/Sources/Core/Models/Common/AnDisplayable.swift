//
//  AnDisplayable.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnDisplayable: Equatable {
  var displayTitle: String { get }
  var groupTitle: String? { get }
}

extension AnDisplayable {
  var groupTitle: String? { nil }
}
