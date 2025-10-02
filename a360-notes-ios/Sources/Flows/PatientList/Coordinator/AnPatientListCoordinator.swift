//
//  AnPatientListCoordinator.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

@MainActor
protocol AnPatientListCoordinatorOutput: AnCoordinator {
  var onLogout: (() -> Void)? { get set }
}

@MainActor
final class AnPatientListCoordinator: AnBaseCoordinator, AnPatientListCoordinatorOutput {
  
  // MARK: - Output
  
  var onLogout: (() -> Void)?
  
  // MARK: - Private Properties
  
  private let navigationController: UINavigationController
  private var consultationCoordinatorOutput: AnConsultationCoordinatorOutput?
  private var patientListViewController: AnPatientListViewController?
  private var patientRecordViewController: AnPatientRecordViewController?
  private var consultationProfileViewController: AnConsultationProfileViewController?
  
  // MARK: - Lifecycle
  
  init(navigationController: UINavigationController) {
    self.navigationController = navigationController
  }
  
  // MARK: - Public Functions
  
  override func start() {
    let viewController: AnPatientListViewController = UIStoryboard(.patientList).instantiateController()
    patientListViewController = viewController
    viewController.onLogout = { [weak self] in
      self?.patientListViewController = nil
      self?.onLogout?()
    }
    viewController.onSelectPatient = { [weak self] patient, activeTab in
      self?.showPatientRecord(patient: patient, activeTab: activeTab)
    }
    viewController.onAddPatient = { [weak self] in
      self?.showAddEditPatient()
    }
    viewController.onStartConsultation = { [weak self] patient in
      self?.runConsultationFlow(patient: patient)
    }
    viewController.onShowFilter = { [weak self] filter in
      self?.showPatientListFilter(forFilter: filter)
    }
    navigationController.setViewControllers([viewController], animated: false)
  }
  
  // MARK: - Private Functions
  
  private func runConsultationFlow(patient: AnPatient, consultation: AnConsultation? = nil) {
    guard AnUserManager.shared.currentUser?.role ?? .admin != .admin else {
      navigationController.showErrorBanner("A360 Admin role cannot run consultations")
      return
    }
    
    let consultationCoordinator = AnConsultationCoordinator(patient: patient, consultation: consultation, navigationController: navigationController)
    consultationCoordinator.finishFlow = { [weak self, weak consultationCoordinator] consultation in
      guard let self else { return }
      removeDependency(consultationCoordinator)
      consultationCoordinatorOutput = nil
      patientRecordViewController?.activateTab(.history)
      consultationProfileViewController?.refresh(consultation: consultation)
    }
    consultationCoordinatorOutput = consultationCoordinator
    addDependency(consultationCoordinator)
    consultationCoordinator.start()
  }
  
  private func showPatientListFilter(forFilter filter: AnPatientListFilter) {
    let viewController: AnPatientListFilterViewController = UIStoryboard(.patientList).instantiateController()
    viewController.filter = filter
    viewController.onApply = { [weak self] newFilter in
      self?.navigationController.dismiss(animated: true) { [weak self] in
        self?.patientListViewController?.filter = newFilter
      }
    }
    
    viewController.onDismiss = { [weak self] in
      self?.navigationController.dismiss(animated: true)
    }
    let patientListFilterNavigationController: UINavigationController = UINavigationController(rootViewController: viewController)
    patientListFilterNavigationController.modalPresentationStyle = .pageSheet
    navigationController.present(patientListFilterNavigationController, animated: true)
  }
  
  private func showPatientRecord(patient: AnPatient, activeTab: AnPatientRecordTab) {
    let viewController: AnPatientRecordViewController = UIStoryboard(.patientList).instantiateController()
    patientRecordViewController = viewController
    viewController.patient = patient
    viewController.activeTab = activeTab
    viewController.onClose = { [weak self] in
      self?.navigationController.popViewController(animated: true)
      self?.patientRecordViewController = nil
    }
    viewController.onStartConsultation = { [weak self] patient in
      self?.runConsultationFlow(patient: patient)
    }
    viewController.onResumeConsultation = { [weak self] patient, consultation in
      self?.runConsultationFlow(patient: patient, consultation: consultation)
    }
    viewController.onShowConsultationProfile = { [weak self] patient, consultation in
      self?.showConsultationProfile(patient: patient, consultation: consultation)
    }
    viewController.onEditPatient = { [weak self] patient in
      self?.showAddEditPatient(patient)
    }
    viewController.onEditPatientSummary = { [weak self] patient in
      self?.onEditPatientSummary(patient)
    }
    viewController.onShowConsultationListFilter = { [weak self] filter in
      self?.showConsultationListFilter(forFilter: filter)
    }
    navigationController.pushViewController(viewController, animated: true)
  }
  
  private func showConsultationListFilter(forFilter filter: AnConsultationListFilter) {
    let viewController: AnConsultationListFilterViewController = UIStoryboard(.patientList).instantiateController()
    viewController.filter = filter
    viewController.onApply = { [weak self] newFilter in
      self?.navigationController.dismiss(animated: true) { [weak self] in
        self?.patientRecordViewController?.consultationListFilter = newFilter
      }
    }
    
    viewController.onDismiss = { [weak self] in
      self?.navigationController.dismiss(animated: true)
    }
    let consultationsNavigationController: UINavigationController = UINavigationController(rootViewController: viewController)
    consultationsNavigationController.modalPresentationStyle = .pageSheet
    navigationController.present(consultationsNavigationController, animated: true)
  }
  
  private func showAddEditPatient(_ patient: AnPatient? = nil) {
    let viewController: AnAddEditPatientViewController = UIStoryboard(.patientList).instantiateController()
    viewController.patient = patient
    viewController.onPatientAdded = { [weak self] patient in
      self?.navigationController.dismiss(animated: true) { [weak self] in
        self?.patientListViewController?.insert(patient: patient)
        self?.showPatientRecord(patient: patient, activeTab: .profile)
      }
    }
    viewController.onPatientUpdated = { [weak self] patient in
      self?.navigationController.dismiss(animated: true) { [weak self] in
        self?.patientListViewController?.refresh(patient: patient)
        self?.patientRecordViewController?.refresh(patient: patient)
      }
    }
    viewController.onDismiss = { [weak self] in
      self?.navigationController.dismiss(animated: true)
    }
    let addEditPatientNavigationController: UINavigationController = UINavigationController(rootViewController: viewController)
    addEditPatientNavigationController.modalPresentationStyle = .pageSheet
    navigationController.present(addEditPatientNavigationController, animated: true)
  }
  
  private func onEditPatientSummary(_ patient: AnPatient) {
    let viewController: AnEditPatientSummaryViewController = UIStoryboard(.patientList).instantiateController()
    viewController.patient = patient
    viewController.onPatientUpdated = { [weak self] patient in
      self?.navigationController.dismiss(animated: true) { [weak self] in
        self?.patientRecordViewController?.refresh(patient: patient)
      }
    }
    viewController.onDismiss = { [weak self] in
      self?.navigationController.dismiss(animated: true)
    }
    let editPatientNavigationController: UINavigationController = UINavigationController(rootViewController: viewController)
    editPatientNavigationController.modalPresentationStyle = .pageSheet
    navigationController.present(editPatientNavigationController, animated: true)
  }
  
  private func showConsultationProfile(patient: AnPatient, consultation: AnConsultation) {
    let viewController: AnConsultationProfileViewController = UIStoryboard(.patientList).instantiateController()
    consultationProfileViewController = viewController
    viewController.patient = patient
    viewController.consultation = consultation
    viewController.onResumeConsultation = { [weak self] patient, consultation in
      self?.runConsultationFlow(patient: patient, consultation: consultation)
    }
    viewController.onClose = { [weak self] updatedConsultation in
      self?.navigationController.popViewController(animated: true)
      self?.consultationProfileViewController = nil
      guard let updatedConsultation else { return }
      self?.patientRecordViewController?.refresh(consultation: updatedConsultation)
    }
    navigationController.pushViewController(viewController, animated: true)
  }
}
