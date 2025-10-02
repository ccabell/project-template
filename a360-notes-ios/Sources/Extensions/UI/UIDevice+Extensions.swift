//
//  UIDevice+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 27.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

extension UIDevice {
  var modelName: String {
    var systemInfo = utsname()
    uname(&systemInfo)
    let machineMirror = Mirror(reflecting: systemInfo.machine)
    let identifier = machineMirror.children.reduce("") { identifier, element in
      guard let value = element.value as? Int8, value != 0 else { return identifier }
      return identifier + String(UnicodeScalar(UInt8(value)))
    }
    return identifier
  }
  
  var isPad: Bool {
    return UIDevice.current.userInterfaceIdiom == .pad
  }
}
