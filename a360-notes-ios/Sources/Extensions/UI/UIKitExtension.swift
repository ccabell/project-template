//
//  UIKitExtension.swift
//  A360Scribe
//
//  Created by Mike Grankin on 18.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SwiftMessages

protocol AnStoryboardIdentifiable {
  static var identifier: String { get }
}

extension AnStoryboardIdentifiable where Self: UIViewController {
  static var identifier: String {
    return String(describing: self)
  }
}

extension UIViewController: AnStoryboardIdentifiable {}

protocol Reusable {
  static var reuseIdentifier: String { get }
}

extension Reusable {
  static var reuseIdentifier: String {
    return String(describing: Self.self)
  }
}

protocol InterfaceBuilderPrototypable {
  static var nib: UINib { get }
}

extension InterfaceBuilderPrototypable {
  static var nib: UINib {
    return UINib(nibName: String(describing: Self.self), bundle: nil)
  }
}

extension UITableView {
  // MARK: - UITableViewCell
  func register<T: UITableViewCell>(_: T.Type) where T: Reusable {
    register(T.self, forCellReuseIdentifier: T.reuseIdentifier)
  }
  
  func register<T: UITableViewCell>(_: T.Type) where T: Reusable, T: InterfaceBuilderPrototypable {
    register(T.nib, forCellReuseIdentifier: T.reuseIdentifier)
  }
  
  func dequeue<T: UITableViewCell>(_: T.Type, for indexPath: IndexPath) -> T where T: Reusable {
    guard let cell = dequeueReusableCell(withIdentifier: T.reuseIdentifier, for: indexPath) as? T else {
      abort()
    }
    return cell
  }
  
  // MARK: - UITableViewHeaderFooterView
  func register<T: UITableViewHeaderFooterView>(_: T.Type) where T: Reusable, T: InterfaceBuilderPrototypable {
    register(T.nib, forHeaderFooterViewReuseIdentifier: T.reuseIdentifier)
  }
  
  func dequeue<T: UITableViewHeaderFooterView>(_: T.Type) -> T where T: Reusable {
    guard let header = dequeueReusableHeaderFooterView(withIdentifier: T.reuseIdentifier) as? T else {
      abort()
    }
    return header
  }
}

extension UIView {
  
  @IBInspectable var borderColor: UIColor? {
    get {
      guard let cgColor = layer.borderColor else { return nil }
      return UIColor(cgColor: cgColor)
    }
    set {
      layer.borderColor = newValue?.cgColor
    }
  }
  
  @IBInspectable var borderWidth: CGFloat {
    get {
      return layer.borderWidth
    }
    set {
      layer.borderWidth = newValue
    }
  }
  
  @IBInspectable var cornerRadius: CGFloat {
    get {
      return layer.cornerRadius
    }
    set {
      layer.cornerRadius = newValue
      layer.masksToBounds = newValue > 0.0
    }
  }
  
  var width: CGFloat {
    get { return self.frame.size.width }
    set { self.frame.size.width = newValue }
  }
  
  var height: CGFloat {
    get { return self.frame.size.height }
    set { self.frame.size.height = newValue }
  }
  
  // swiftlint:disable:next identifier_name
  var y: CGFloat {
    get { return self.frame.origin.y }
    set { self.frame.origin.y = newValue }
  }
  
  // swiftlint:disable:next identifier_name
  var x: CGFloat {
    get { return self.frame.origin.x }
    set { self.frame.origin.x = newValue }
  }
  
  var bottom: CGFloat {
    get { return self.frame.origin.y + self.height }
    set { self.frame.origin.y = newValue - self.height }
  }
  
  var left: CGFloat {
    get { return self.frame.origin.x }
    set { self.frame.origin.x = newValue }
  }
  
  var centerX: CGFloat {
    get { return self.center.x }
    set { self.center = CGPoint(x: newValue, y: self.centerY) }
  }
  
  var centerY: CGFloat {
    get { return self.center.y }
    set { self.center = CGPoint(x: self.centerX, y: newValue) }
  }
  
  var origin: CGPoint {
    get { return self.frame.origin }
    set { self.frame.origin = newValue }
  }
  
  var size: CGSize {
    get { return self.frame.size }
    set { self.frame.size = newValue }
  }
  
  func findSubviews<T: UIView>(subclassOf: T.Type) -> [T] {
    return recursiveSubviews.compactMap { $0 as? T }
  }
  
  var recursiveSubviews: [UIView] {
    return subviews + subviews.flatMap { $0.recursiveSubviews }
  }
}

extension UIViewController {
  func showErrorBanner(_ title: String, subtitle: String? = nil, duration: TimeInterval = GlobalConstants.bannerDuration) {
    showBanner(title, subtitle: subtitle, color: .errorMedium, duration: duration, haptic: .error, iconName: "exclamationmark.circle.fill")
  }
  
  func showSuccessBanner(_ title: String, subtitle: String? = nil) {
    showBanner(title, subtitle: subtitle, color: .primarySoft, duration: 2.0, haptic: .success, iconName: "checkmark.circle.fill")
  }
  
  func showInfoBanner(_ title: String, subtitle: String? = nil) {
    showBanner(title, subtitle: subtitle, color: .warningMedium, haptic: .warning, iconName: "info.circle.fill")
  }
  
  func showLogoutTimerBanner(duration: TimeInterval) {
    let formatedDuration = duration.formatedDuration
    let subtitleMessage = "Your session will expire in \(formatedDuration) due to inactivity."
    showBanner("Session Timeout Warning", subtitle: subtitleMessage, color: .warningMedium, duration: duration, haptic: .warning, iconName: "exclamationmark.triangle", id: GlobalConstants.logoutTimerBannerId)
  }
  
  @MainActor
  private func showBanner(_ title: String, subtitle: String? = nil, color: UIColor, duration: TimeInterval = GlobalConstants.bannerDuration, haptic: SwiftMessages.Haptic, iconName: String, id: String? = nil) {
    guard UIApplication.shared.applicationState == .active,
          let statusIcon = UIImage(systemName: iconName, withConfiguration: UIImage.SymbolConfiguration(scale: .large))?.withTintColor(color, renderingMode: .alwaysOriginal),
          let timedCardView = try? SwiftMessages.viewFromNib(named: "AnTimedCardView"),
          let messageView = timedCardView as? AnTimedCardView
    else {
      return
    }
    
    messageView.configure(title: title, subtitle: subtitle, backgroundColor: .surfaceSoft, foregroundColor: .textPrimary, iconImage: statusIcon, progressColor: color, duration: duration)
    messageView.defaultHaptic = haptic
    messageView.buttonTapHandler = { _ in
      SwiftMessages.hide()
    }
    messageView.tapHandler = { _ in
      SwiftMessages.hide()
    }
    if let id {
      messageView.id = id
    }
    
    var config = SwiftMessages.Config()
    config = SwiftMessages.defaultConfig
    config.duration = .seconds(seconds: duration)
    config.eventListeners.append { event in
      if case .didShow(let view) = event,
         let messageView = view as? AnTimedCardView {
        messageView.startTimerAnimation()
      }
    }
    SwiftMessages.show(config: config, view: messageView)
  }
  
  func dismissLogoutTimerBanner() {
    guard SwiftMessages.count(id: GlobalConstants.logoutTimerBannerId) > 0 else { return }
    SwiftMessages.hide(id: GlobalConstants.logoutTimerBannerId)
  }
}

extension UINavigationBar {
  func configureAppearance(backgroundColor: UIColor? = nil, titleColor: UIColor? = nil, removeShadow: Bool = false) {
    let appearance = UINavigationBarAppearance()
    appearance.configureWithDefaultBackground()
    if let backgroundColor {
      appearance.backgroundColor = backgroundColor
    }
    if let titleColor {
      appearance.titleTextAttributes = [.foregroundColor: titleColor]
    }
    if removeShadow {
      appearance.shadowColor = .clear
    }
    standardAppearance = appearance
    scrollEdgeAppearance = appearance
  }
}
