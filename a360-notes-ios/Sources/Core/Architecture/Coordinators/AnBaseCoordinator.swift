//
//  AnBaseCoordinator.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

@MainActor
class AnBaseCoordinator: NSObject, AnCoordinator {
  
  // MARK: - Private Properties
  
  private var childCoordinators: [AnCoordinator] = []
  
  // MARK: - Public Properties
  
  var dependencies: [AnCoordinator] {
    childCoordinators
  }
  
  // MARK: - Lifecycle
  
  override init() {
    super.init()
    print("\(type(of: self)) init")
  }
  
  deinit {
    print("\(type(of: self)) deinit")
  }
  
  // MARK: - Public Functions
  
  func start() {
    assertionFailure("start() must be overridden in subclasses")
  }
  
  func addDependency(_ coordinator: AnCoordinator) {
    guard !childCoordinators.contains(where: { $0 === coordinator }) else { return }
    childCoordinators.append(coordinator)
  }
  
  func removeDependency(_ coordinator: AnCoordinator?) {
    guard let coordinator else { return }
    childCoordinators.removeAll { $0 === coordinator }
  }
  
  func removeAllDependencies() {
    childCoordinators.removeAll()
  }
}
