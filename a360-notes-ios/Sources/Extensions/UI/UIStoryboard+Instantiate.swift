//
//  UIStoryboard+Instantiate.swift
//  A360Scribe
//
//  Created by Mike Grankin on 18.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

enum AnStoryboard: String {
  case login = "LoginFlow"
  case patientList = "PatientListFlow"
  case consultation = "ConsultationFlow"
}

extension UIStoryboard {
  convenience init(_ story: AnStoryboard) {
    self.init(name: story.rawValue, bundle: nil)
  }
  
  func instantiateController<T: UIViewController>() -> T {
    guard let viewController = self.instantiateViewController(withIdentifier: T.identifier) as? T else {
      fatalError("Could not load view controller with identifier\(T.identifier)")
    }
    return viewController
  }
}
