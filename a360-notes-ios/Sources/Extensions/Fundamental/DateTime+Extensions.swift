//
//  TimeInterval+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 26.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

extension TimeInterval {
  var formatedDuration: String {
    let formatter = DateComponentsFormatter()
    formatter.allowedUnits = self < 60 ? [.second] : [.minute, .second]
    formatter.unitsStyle = .full
    formatter.zeroFormattingBehavior = .dropAll
    var result = formatter.string(from: self) ?? "\(Int(self)) seconds"
    result = result.replacingOccurrences(of: ",", with: "")
    return result
  }
}

extension Date {
  static var minAvailableDate: Date {
    return Calendar.current.date(from: DateComponents(year: 1900, month: 1, day: 1)) ?? .distantPast
  }
}
