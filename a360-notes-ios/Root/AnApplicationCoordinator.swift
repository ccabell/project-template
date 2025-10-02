//
//  AnApplicationCoordinator.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

final class AnApplicationCoordinator: AnBaseCoordinator {
  
  // MARK: - Private Properties
  
  private let window: UIWindow
  private var rootNavigationController = UINavigationController()
  private var loginCoordinatorOutput: AnLoginCoordinatorOutput?
  private var patientListCoordinatorOutput: AnPatientListCoordinatorOutput?
  
  // MARK: - Lifecycle
  
  init(window: UIWindow) {
    self.window = window
  }
  
  // MARK: - Public Functions
  
  override func start() {
    window.rootViewController = rootNavigationController
    window.makeKeyAndVisible()
    runLoginFlow()
  }
  
  // MARK: - Private Functions
  
  private func runLoginFlow() {
    let loginCoordinator = AnLoginCoordinator(navigationController: rootNavigationController)
    loginCoordinator.finishFlow = { [weak self, weak loginCoordinator] in
      guard let self else { return }
      removeDependency(loginCoordinator)
      loginCoordinatorOutput = nil
      runPatientListFlow()
    }
    addDependency(loginCoordinator)
    loginCoordinatorOutput = loginCoordinator
    loginCoordinator.start()
  }
  
  private func runPatientListFlow() {
    let patientListCoordinator = AnPatientListCoordinator(navigationController: rootNavigationController)
    patientListCoordinator.onLogout = { [weak self, weak patientListCoordinator] in
      guard let self else { return }
      removeDependency(patientListCoordinator)
      patientListCoordinatorOutput = nil
      resetRoot()
      runLoginFlow()
    }
    patientListCoordinatorOutput = patientListCoordinator
    addDependency(patientListCoordinator)
    patientListCoordinator.start()
  }
  
  private func resetRoot() {
    let newNavigationController = UINavigationController()
    rootNavigationController = newNavigationController
    window.rootViewController = newNavigationController
  }
}
