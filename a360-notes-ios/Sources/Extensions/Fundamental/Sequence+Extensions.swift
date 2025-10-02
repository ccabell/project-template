//
//  Sequence+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.09.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

extension Sequence {
  func uniqued<T: Hashable>(by keySelector: (Element) -> T) -> [Element] {
    var seenKeys = Set<T>()
    return self.filter { seenKeys.insert(keySelector($0)).inserted }
  }
}
