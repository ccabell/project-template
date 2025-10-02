//
//  AnSwipeCellTransition.swift
//  A360Scribe
//
//  Created by Mike Grankin on 01.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SwipeCellKit

final class AnSwipeCellTransition: SwipeActionTransitioning {
  
  // MARK: - Private Properties
  
  private let scaleTransition: ScaleTransition
  private let needsSeparator: Bool
  
  // MARK: - Lifecycle
  
  init(needsSeparator: Bool, duration: Double = 0.2, initialScale: CGFloat = 0.5, threshold: CGFloat = 0.4) {
    self.scaleTransition = ScaleTransition(duration: duration, initialScale: initialScale, threshold: threshold)
    self.needsSeparator = needsSeparator
  }
  
  // MARK: - SwipeActionTransitioning
  
  func didTransition(with context: SwipeActionTransitioningContext) {
    scaleTransition.didTransition(with: context)
    
    guard needsSeparator, !(context.button.layer.sublayers?.contains(where: { $0.name == "separator" }) ?? false) else { return }
    
    let separatorLayer = CALayer()
    separatorLayer.name = "separator"
    separatorLayer.frame = CGRect(x: 0.0, y: 0.0, width: 1.0, height: context.button.bounds.height)
    separatorLayer.backgroundColor = UIColor.surfaceStrong.cgColor
    context.button.layer.addSublayer(separatorLayer)
  }
}
