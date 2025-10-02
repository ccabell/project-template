//
//  AnRecentUserCell.swift
//  A360Scribe
//
//  Created by Mike Grankin on 06.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

final class AnRecentUserCell: UITableViewCell, Reusable, InterfaceBuilderPrototypable {
  
  // MARK: - Outlets
  
  @IBOutlet private weak var photoImageView: UIImageView!
  @IBOutlet private weak var nameLabel: UILabel!
  @IBOutlet private weak var emailLabel: UILabel!
  
  // MARK: - Output
  
  var onDelete: ((_ user: AnUser, _ source: UIPopoverPresentationControllerSourceItem?) -> Void)?
  
  // MARK: - Private Properties
  
  private var user: AnUser?
  
  // MARK: - Public Functions
  
  func setup(user: AnUser) {
    self.user = user
    nameLabel.text = user.displayName
    emailLabel.text = user.username
    photoImageView.image = UIImage.initialsImage(displayName: user.nameForInitials, diameter: photoImageView.bounds.width, backgroundColor: user.avatarColor)
  }
  
  // MARK: - Actions
  
  @IBAction private func onDeleteAction(_ sender: UIButton) {
    guard let user else { return }
    onDelete?(user, sender)
  }
}
