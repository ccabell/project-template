//
//  AppDelegate.swift
//  A360Scribe
//
//  Created by Mike Grankin on 29.01.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import IQKeyboardManagerSwift
import IQKeyboardToolbarManager
import UserNotifications

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
  
  // MARK: - Application Lifecycle
  
  func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    configureKeyboardManager()
    configureNotificationManager()
    return true
  }
  
  // MARK: - UISceneSession Lifecycle
  
  func application(_ application: UIApplication, configurationForConnecting connectingSceneSession: UISceneSession, options: UIScene.ConnectionOptions) -> UISceneConfiguration {
    return UISceneConfiguration(name: "Default Configuration", sessionRole: connectingSceneSession.role)
  }
  
  func application(_ application: UIApplication, didDiscardSceneSessions sceneSessions: Set<UISceneSession>) {
    // No action needed when scene sessions are discarded
  }
  
  func applicationWillTerminate(_ application: UIApplication) {
    AnSessionManager.shared.logout()
  }
  
  // MARK: - Private Functions
  
  private func configureKeyboardManager() {
    IQKeyboardManager.shared.isEnabled = true
    IQKeyboardManager.shared.keyboardDistance = 16.0
    IQKeyboardManager.shared.resignOnTouchOutside = true
    IQKeyboardToolbarManager.shared.isEnabled = true
    IQKeyboardToolbarManager.shared.toolbarConfiguration.useTextInputViewTintColor = true
    IQKeyboardToolbarManager.shared.deepResponderAllowedContainerClasses.append(UIStackView.self)
  }
  
  private func configureNotificationManager() {
    UNUserNotificationCenter.current().delegate = self
    AnNotificationManager.shared.requestAuthorizationIfNeeded()
  }
}

// MARK: - UNUserNotificationCenterDelegate

extension AppDelegate: UNUserNotificationCenterDelegate {
  
  func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
    print(response.notification.request.content.userInfo)
    completionHandler()
  }
  
  func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
    completionHandler([.list, .banner, .badge, .sound])
  }
}
