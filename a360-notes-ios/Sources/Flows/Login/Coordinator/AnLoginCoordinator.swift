//
//  AnLoginCoordinator.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

@MainActor
protocol AnLoginCoordinatorOutput: AnCoordinator {
  var finishFlow: (() -> Void)? { get set }
}

@MainActor
final class AnLoginCoordinator: AnBaseCoordinator, AnLoginCoordinatorOutput {
  
  // MARK: - Output
  
  var finishFlow: (() -> Void)?
  
  // MARK: - Private Properties
  
  private let navigationController: UINavigationController
  
  // MARK: - Lifecycle
  
  init(navigationController: UINavigationController) {
    self.navigationController = navigationController
  }
  
  // MARK: - Public Functions
  
  override func start() {
    guard let latestUser = AnUserManager.shared.getLastLoggedInUser() else {
      showNewLogin()
      return
    }
    showQuickLogin(user: latestUser)
  }
  
  // MARK: - Private Functions
  
  private func showNewLogin() {
    let viewController = UIStoryboard(.login).instantiateController() as AnLoginViewController
    viewController.finishFlow = finishFlow
    viewController.onSelectUser = showRecentsList
    navigationController.setViewControllers([viewController], animated: false)
  }
  
  private func showQuickLogin(user: AnUser) {
    let viewController = UIStoryboard(.login).instantiateController() as AnRecentLoginViewController
    viewController.user = user
    viewController.finishFlow = finishFlow
    viewController.onAddUser = showNewLogin
    viewController.onChangeUser = showRecentsList
    navigationController.setViewControllers([viewController], animated: false)
  }
  
  private func showRecentsList() {
    let viewController = UIStoryboard(.login).instantiateController() as AnRecentUsersViewController
    viewController.onAddUser = showNewLogin
    viewController.onSelectUser = showQuickLogin(user:)
    navigationController.setViewControllers([viewController], animated: false)
  }
}
