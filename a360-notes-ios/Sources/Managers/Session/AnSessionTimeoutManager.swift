//
//  AnSessionTimeoutManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 25.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import LocalAuthentication

final class AnSessionTimeoutManager: NSObject {
  
  // MARK: - Public Properties
  
  static let shared = AnSessionTimeoutManager()
  
  // MARK: - Private Properties
  
  private var timer: Timer?
  private var lastInteractionDate = Date()
  private var isWarningShown = false
  private var isAppActive: Bool {
    let state = UIApplication.shared.applicationState
    return state == .active
  }
  private var deviceProtected: Bool {
    LAContext().canEvaluatePolicy(.deviceOwnerAuthentication, error: nil)
  }
  
  // MARK: - Lifecycle
  
  override init() {
    super.init()
    NotificationCenter.default.addObserver(self, selector: #selector(protectedDataBecameUnavailable), name: UIApplication.protectedDataWillBecomeUnavailableNotification, object: nil)
  }
  
  deinit {
    NotificationCenter.default.removeObserver(self)
  }
  
  // MARK: - Public Functions
  
  func startMonitoring() {
    timer?.invalidate()
    timer = Timer.scheduledTimer(timeInterval: 1.0, target: self, selector: #selector(checkTimeout), userInfo: nil, repeats: true)
    updateTimer()
  }
  
  func stopMonitoring() {
    timer?.invalidate()
    timer = nil
  }
  
  func updateTimer() {
    guard timer != nil else { return }
    lastInteractionDate = Date()
    guard isWarningShown else { return }
    UIApplication.topViewController?.dismissLogoutTimerBanner()
    isWarningShown = false
  }
  
  func enableInteractionTracking(in window: UIWindow?) {
    let tap = UITapGestureRecognizer(target: self, action: #selector(userDidInteract))
    tap.cancelsTouchesInView = false
    tap.delegate = self
    window?.addGestureRecognizer(tap)
  }
  
  // MARK: - Private Functions
  
  @objc
  private func userDidInteract() {
    updateTimer()
  }
  
  @objc
  private func checkTimeout() {
    guard timer != nil, isAppActive else { return }
    
    let difference = Date().timeIntervalSince(lastInteractionDate)
    switch difference {
    case GlobalConstants.InactivityTimeout.idleWarningAfter.rawValue..<GlobalConstants.InactivityTimeout.logoutAfter.rawValue:
      guard !isWarningShown else { return }
      isWarningShown = true
      let bannerDuration = GlobalConstants.InactivityTimeout.logoutAfter.rawValue - difference
      UIApplication.topViewController?.showLogoutTimerBanner(duration: bannerDuration)
    case GlobalConstants.InactivityTimeout.logoutAfter.rawValue...:
      timer?.invalidate()
      performLogout()
    default:
      return
    }
  }
  
  @objc
  private func protectedDataBecameUnavailable() {
    guard !deviceProtected else { return }
    stopMonitoring()
    performLogout()
  }
  
  private func performLogout() {
    NotificationCenter.default.post(name: GlobalConstants.Notifications.performLogout.name, object: nil)
  }
}

// MARK: - UIGestureRecognizerDelegate

extension AnSessionTimeoutManager: UIGestureRecognizerDelegate {
  func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
    return true
  }
}
