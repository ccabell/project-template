//
//  SceneDelegate.swift
//  A360Scribe
//
//  Created by Mike Grankin on 29.01.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
  
  var window: UIWindow?
  private var applicationCoordinator: AnApplicationCoordinator?
  
  func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
    guard let windowScene = scene as? UIWindowScene else { return }
    let window = UIWindow(windowScene: windowScene)
    self.window = window
    let coordinator = AnApplicationCoordinator(window: window)
    applicationCoordinator = coordinator
    coordinator.start()
    AnSessionTimeoutManager.shared.enableInteractionTracking(in: window)
  }
  
  func sceneDidDisconnect(_ scene: UIScene) { }
  func sceneDidBecomeActive(_ scene: UIScene) { }
  func sceneWillResignActive(_ scene: UIScene) { }
  func sceneWillEnterForeground(_ scene: UIScene) { }
  func sceneDidEnterBackground(_ scene: UIScene) { }
}
