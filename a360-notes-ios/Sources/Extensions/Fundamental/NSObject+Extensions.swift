//
//  NSObject+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

extension NSObject {
  var className: String {
    return String(describing: type(of: self))
  }
  
  static var className: String {
    return String(describing: self)
  }
}
