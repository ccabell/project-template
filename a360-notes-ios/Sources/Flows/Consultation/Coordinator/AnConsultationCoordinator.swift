//
//  AnConsultationCoordinator.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

@MainActor
protocol AnConsultationCoordinatorOutput: AnCoordinator {
  var finishFlow: ((AnConsultation?) -> Void)? { get set }
}

@MainActor
final class AnConsultationCoordinator: AnBaseCoordinator, AnConsultationCoordinatorOutput {
  
  // MARK: - Output
  
  var finishFlow: ((AnConsultation?) -> Void)?
  
  // MARK: - Private Properties
  
  private let navigationController: UINavigationController
  private let patient: AnPatient?
  private let consultation: AnConsultation?
  
  // MARK: - Lifecycle
  
  init(patient: AnPatient, consultation: AnConsultation?, navigationController: UINavigationController) {
    self.navigationController = navigationController
    self.patient = patient
    self.consultation = consultation
  }
  
  // MARK: - Public Functions
  
  override func start() {
    let viewController: AnConsultationViewController = UIStoryboard(.consultation).instantiateController()
    viewController.patient = patient
    viewController.consultation = consultation
    viewController.finishFlow = { [weak self] consultation in
      self?.navigationController.popViewController(animated: true)
      self?.finishFlow?(consultation)
    }
    navigationController.pushViewController(viewController, animated: true)
  }
}
