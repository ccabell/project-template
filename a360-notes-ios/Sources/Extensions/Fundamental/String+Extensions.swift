//
//  String+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 02.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

extension String {
  
  func trimmed() -> String {
    return self.trimmingCharacters(in: .whitespacesAndNewlines)
  }
  
  var percentEncoded: String {
    let fastAPIForbiddenCharacters = "&=+#," // optionally if we want to follow rfc3986 standard we can use next set ":/?#[]@!$&'()*+,;="
    var allowed = CharacterSet.urlQueryAllowed
    allowed.remove(charactersIn: fastAPIForbiddenCharacters)
    return addingPercentEncoding(withAllowedCharacters: allowed) ?? ""
  }
  
  var textColor: UIColor {
    let offsetBasis: UInt32 = 2166136261
    let prime: UInt32 = 16777619
    let hash = unicodeScalars.reduce(offsetBasis) { accumulator, scalar in (accumulator ^ UInt32(scalar.value)) &* prime }
    let baseHue = CGFloat(hash % 360) / 360.0
    let rawHue = baseHue + 0.618033988749895
    let hue = rawHue > 1.0 ? rawHue - 1.0 : rawHue
    return UIColor(hue: hue, saturation: 0.45, brightness: 0.85, alpha: 1.0)
  }
  
  var avatarColor: UIColor {
    let colors: [UIColor] = [.primarySoft, .textPrimary, .successMedium, .warningMedium, .errorMedium, .secondarySoft]
    let hashValue: Int = utf16.reduce(0) { accumulator, unit in accumulator + Int(unit) }
    let index: Int = hashValue % colors.count
    guard index < colors.count else { return colors[0] }
    return colors[index]
  }
}

extension Optional where Wrapped == String {
  
  /// - Returns: `true` if the string is `nil` or empty
  var isEmptyOrNil: Bool {
    return self?.isEmpty ?? true
  }
  
  /// Returns the wrapped string if non-empty; otherwise returns `defaultValue`.
  func or(_ defaultValue: String) -> String {
    guard let self, !self.isEmpty else { return defaultValue }
    return self
  }
}
