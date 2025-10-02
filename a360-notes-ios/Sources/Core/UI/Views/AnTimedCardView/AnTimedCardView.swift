//
//  AnTimedCardView.swift
//  A360Scribe
//
//  Created by Mike Grankin on 12.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SwiftMessages

final class AnTimedCardView: MessageView {
  
  // MARK: - Outlets
  
  @IBOutlet private weak var timeIndicatorProgressView: UIProgressView!
  
  // MARK: - Private properties
  
  private var displayDuration = GlobalConstants.bannerDuration
  
  // MARK: - Public functions
  
  func configure(title: String, subtitle: String? = nil, backgroundColor: UIColor, foregroundColor: UIColor, iconImage: UIImage, progressColor: UIColor, duration: TimeInterval) {
    guard let closeIcon = UIImage(systemName: "xmark.circle") else { return }
    
    configureTheme(backgroundColor: .surfaceSoft, foregroundColor: .textPrimary, iconImage: iconImage)
    titleLabel?.text = title
    if let subtitle {
      bodyLabel?.text = subtitle
      bodyLabel?.textColor = .textBody
    } else {
      bodyLabel?.isHidden = true
    }
    iconImageView?.image = iconImage
    button?.setImage(closeIcon, for: .normal)
    button?.setTitle(nil, for: .normal)
    button?.backgroundColor = .surfaceSoft
    button?.tintColor = .secondaryStrong
    backgroundView.cornerRadius = 8.0
    backgroundView.borderColor = .secondarySoft
    backgroundView.borderWidth = 1.0
    
    displayDuration = duration
    timeIndicatorProgressView.progress = 1.0
    timeIndicatorProgressView.progressTintColor = progressColor
    timeIndicatorProgressView.trackTintColor = progressColor.withAlphaComponent(0.1)
  }
  
  func startTimerAnimation() {
    UIView.animate(withDuration: 0.0, animations: {
      self.timeIndicatorProgressView.layoutIfNeeded()
    }, completion: { _ in
      self.timeIndicatorProgressView.progress = 0.0
      UIView.animate(withDuration: self.displayDuration, delay: 0.0, options: .curveLinear) {
        self.timeIndicatorProgressView.layoutIfNeeded()
      }
    })
  }
}
