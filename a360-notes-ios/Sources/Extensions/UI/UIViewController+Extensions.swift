//
//  UIViewController+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

extension UIViewController {
  
  var isPresentedTypeOfController: Bool {
    let isInstanceOfUIKitPresented = ["_UIContextMenuActionsOnlyViewController", "UIAlertController"].contains(self.className)
    return isInstanceOfUIKitPresented
  }
  
  // MARK: - Navigation Title with Subtitle
  
  internal func setNavigationTitle(_ title: String?, subtitle: String?) {
    guard let subtitle, !subtitle.isEmpty else {
      navigationItem.title = title
      return
    }
    
    let titleLabel = UILabel()
    titleLabel.text = title
    titleLabel.font = .systemFont(ofSize: 17.0, weight: .semibold)
    
    let subtitleLabel = UILabel()
    subtitleLabel.text = subtitle
    subtitleLabel.font = .systemFont(ofSize: 12.0, weight: .regular)
    subtitleLabel.textColor = .gray
    
    let stackView = UIStackView(arrangedSubviews: [titleLabel, subtitleLabel])
    stackView.axis = .vertical
    stackView.alignment = .center
    
    navigationItem.titleView = stackView
  }
  
  internal func convertNavigationTitleToImage() {
    guard let titleImageName = navigationItem.title,
          let image = UIImage(named: titleImageName) else { return }
    let imageView = UIImageView(image: image)
    imageView.contentMode = .scaleAspectFit
    imageView.sizeToFit()
    navigationItem.titleView = imageView
  }

  // MARK: - HUD
  
  @MainActor
  func showHUD() {
    guard currentHUD() == nil else { return }
    AnHUDOverlayView.show(in: view)
  }
  
  func showHUD(in parent: UIView, blocksTouches: Bool = true, unhideParent: Bool = false) {
    guard currentHUD() == nil else { return }
    if unhideParent {
      parent.isHidden = false
    }
    AnHUDOverlayView.show(in: parent, blocksTouches: blocksTouches)
  }

  @MainActor
  func hideHUD(hideParent: Bool = false) {
    guard let hud = currentHUD() else { return }
    hud.hide()
    if hud.superview != view, hideParent {
      hud.superview?.isHidden = true
    }
  }
  
  private func currentHUD() -> AnHUDOverlayView? {
    view.findSubviews(subclassOf: AnHUDOverlayView.self).first
  }
}
