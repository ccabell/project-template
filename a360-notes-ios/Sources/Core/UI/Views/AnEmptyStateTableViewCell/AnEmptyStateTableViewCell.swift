//
//  AnEmptyStateTableViewCell.swift
//  A360Scribe
//
//  Created by Mike Grankin on 11.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

final class AnEmptyStateTableViewCell: UITableViewCell, Reusable, InterfaceBuilderPrototypable {
  
  // MARK: - Outlets
  
  @IBOutlet private weak var emptyStateView: AnEmptyStateView!
  
  // MARK: - Lifecycle
  
  override func layoutSubviews() {
    super.layoutSubviews()
    separatorInset = UIEdgeInsets(top: 0.0, left: bounds.width, bottom: 0.0, right: 0.0)
  }
  
  // MARK: - Public Functions
  
  func configure(title: String,
                 subtitle: String,
                 icon: String? = nil,
                 inlineIcon: String? = nil,
                 titleColor: UIColor = .secondarySoft,
                 subtitleIconColor: UIColor = .primaryMedium,
                 subtitleIconSize: CGFloat = 20.0) {
    emptyStateView.titleText = title
    emptyStateView.subtitleText = subtitle
    emptyStateView.titleIconName = icon
    emptyStateView.inlineIconName = inlineIcon
    emptyStateView.titleIconColor = titleColor
    emptyStateView.subtitleInlineIconColor = subtitleIconColor
    emptyStateView.subtitleInlineIconSize = subtitleIconSize
  }
}
