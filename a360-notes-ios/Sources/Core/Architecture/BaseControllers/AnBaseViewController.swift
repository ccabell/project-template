//
//  AnBaseViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import IQKeyboardReturnManager
#if !(RELEASE)
import FNMNetworkMonitor
#endif

class AnBaseViewController: UIViewController {
  
  let keyboardReturnManager = IQKeyboardReturnManager()
#if !(RELEASE)
  private var debugViewController: UIViewController?
#endif
  
  deinit {
    print("\(type(of: self)) deinit")
  }
  
  override func viewDidLoad() {
    super.viewDidLoad()
    print("\(type(of: self)) init")
    keyboardReturnManager.addResponderSubviews(of: view, recursive: true)
  }
}

#if !(RELEASE)
extension AnBaseViewController: UINavigationControllerDelegate {
  
  // MARK: - Motion Handling
  
  override open func motionEnded(_ motion: UIEvent.EventSubtype, with event: UIEvent?) {
    guard motion == .motionShake else {
      super.motionEnded(motion, with: event)
      return
    }
    handleNetworkMonitor()
  }
  
  // MARK: - Private Functions
  
  private func handleNetworkMonitor() {
    if !FNMNetworkMonitor.shared.isMonitoring() {
      showAlert("Activate NetworkMonitor logging?", title: "Shake detected", proceedTitle: "Activate", proceedStyle: .default, cancelTitle: "Cancel") {
        FNMNetworkMonitor.registerToLoadingSystem()
        FNMNetworkMonitor.shared.startMonitoring()
      }
    } else {
      showNetworkMonitor()
    }
  }
  
  private func showNetworkMonitor() {
    let networkMonitorNavigationController = UINavigationController()
    networkMonitorNavigationController.delegate = self
    networkMonitorNavigationController.modalPresentationStyle = .pageSheet
    networkMonitorNavigationController.navigationBar.isTranslucent = false
    networkMonitorNavigationController.navigationBar.barTintColor = .systemBackground
    networkMonitorNavigationController.view.backgroundColor = .systemBackground
    FNMNetworkMonitor.shared.showDebugListingViewController(presentingNavigationController: networkMonitorNavigationController)
    debugViewController = networkMonitorNavigationController.viewControllers.first
    present(networkMonitorNavigationController, animated: true)
  }
  
  // MARK: - UINavigationControllerDelegate
  
  public func navigationController(_ navigationController: UINavigationController, didShow viewController: UIViewController, animated: Bool) {
    guard viewController == debugViewController else { return }
    viewController.navigationItem.leftBarButtonItem = UIBarButtonItem(systemItem: .close, primaryAction: UIAction { [weak self] _ in
      self?.dismiss(animated: true)
    })
  }
}
#endif
