//
//  UIApplication+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

extension UIApplication {
  
  // MARK: - Class Functions
  
  class var topViewController: UIViewController? {
    return UIApplication.shared.topViewController()
  }
  
  class var applicationKeyWindow: UIWindow? {
    return UIApplication.shared.connectedScenes.flatMap { ($0 as? UIWindowScene)?.windows ?? [] }.first { $0.isKeyWindow }
  }
  
  @MainActor
  func waitUntilActiveIfNeeded() async throws {
    guard applicationState != .active else { return }
    try await withThrowingTaskGroup(of: Void.self) { group in
      group.addTask {
        for await _ in NotificationCenter.default.notifications(named: UIApplication.didBecomeActiveNotification) { break }
      }
      group.addTask {
        try await Task.sleep(for: .seconds(60))
        throw AnError("Application did not become active within 60 seconds. Please try again.")
      }
      do {
        try await group.next()
      } catch {
        group.cancelAll()
        throw error
      }
      group.cancelAll()
    }
  }
  
  // MARK: - Private Functions
  
  private func topViewController(base: UIViewController? = applicationKeyWindow?.rootViewController, forPopover: Bool = false) -> UIViewController? {
    if let tabBarController = base as? UITabBarController {
      let moreNavigationController = tabBarController.moreNavigationController
      
      if let topController = moreNavigationController.topViewController,
         topController.view.window != nil {
        return topViewController(base: topController)
      } else if let selected = tabBarController.selectedViewController {
        return topViewController(base: selected, forPopover: forPopover)
      }
    }
    
    if !forPopover {
      if let navigationController = base as? UINavigationController {
        return topViewController(base: navigationController.visibleViewController)
      }
      
      if let presented = base?.presentedViewController {
        return topViewController(base: presented)
      }
      
      if base?.isPresentedTypeOfController ?? false,
         let presenting = base?.presentingViewController {
        return topViewController(base: presenting, forPopover: true)
      }
      
      return base
    } else {
      if let navigationController = base as? UINavigationController {
        return topViewController(base: navigationController.viewControllers.last, forPopover: true)
      }
      
      return base
    }
  }
}
