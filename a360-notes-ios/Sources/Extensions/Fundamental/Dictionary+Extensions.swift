//
//  Dictionary+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

extension Dictionary where Key == String, Value == Any? {
  func jsonData() throws -> Data {
    return try JSONSerialization.data(withJSONObject: self)
  }
}
