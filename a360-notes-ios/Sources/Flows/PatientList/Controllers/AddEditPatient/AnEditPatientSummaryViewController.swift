//
//  AnEditPatientSummaryViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 23.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnEditPatientSummaryOutput {
  var onPatientUpdated: ((AnPatient) -> Void)? { get set }
  var onDismiss: (() -> Void)? { get set }
  var patient: AnPatient? { get set }
}

final class AnEditPatientSummaryViewController: AnBaseViewController, AnEditPatientSummaryOutput {
  
  // MARK: - Output
  
  var onPatientUpdated: ((AnPatient) -> Void)?
  var onDismiss: (() -> Void)?
  var patient: AnPatient?
  
  // MARK: - Outlets
  
  @IBOutlet private weak var saveButton: UIBarButtonItem!
  @IBOutlet private weak var summaryTextView: UITextView!
  
  // MARK: - Private Properties
  
  private lazy var patientService: AnPatientService = AnAPIService()
  internal var isUpdated = false {
    didSet {
      saveButton.isEnabled = isUpdated
    }
  }
  private let placeholderText: String = "Enter Patient Summary"
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureNavigationBar()
    configureUI()
  }
  
  // MARK: - Actions
  
  @IBAction private func onCancelAction(_ sender: UIButton) {
    view.endEditing(true)
    guard isUpdated else {
      onDismiss?()
      return
    }
    showAlert("All unsaved data will be lost, do you want to continue?", proceedTitle: "Yes", proceedStyle: .destructive, cancelTitle: "No", source: sender) { [weak self] in
      self?.onDismiss?()
    }
  }
  
  @IBAction private func onSaveAction(_ sender: Any) {
    view.endEditing(true)
    updatePatient()
  }
  
  // MARK: - Private Functions
  
  private func configureNavigationBar() {
    navigationController?.navigationBar.configureAppearance(backgroundColor: .backgroundDefault, removeShadow: false)
  }
  
  private func configureUI() {
    guard let patientId = patient?.id else { return }
    
    Task {

      defer {
        hideHUD()
      }

      do {
        showHUD()
        let patientProfile: AnPatient = try await patientService.getPatient(patientId)
        patient = patientProfile
        if let summary = patient?.summary, !summary.isEmpty {
          summaryTextView.text = summary
          summaryTextView.textColor = .label
        } else {
          summaryTextView.text = placeholderText
          summaryTextView.textColor = .defaultText
        }
      } catch {
        showErrorBanner(error.localizedDescription)
      }
    }
  }
  
  private func updatePatient() {
    Task {

      defer {
        saveButton.isEnabled = true
        hideHUD()
      }

      saveButton.isEnabled = false
      guard let patientId = patient?.id else { return }
      let params = AnPatientSummaryParams(id: patientId, summary: summaryTextView.text == placeholderText ? "" : summaryTextView.text)
      do {
        showHUD()
        let updatedPatient = try await patientService.updatePatientSummary(parameters: params)
        onPatientUpdated?(updatedPatient)
      } catch {
        showErrorBanner(error.localizedDescription)
      }
    }
  }
}

// MARK: - UITextViewDelegate

extension AnEditPatientSummaryViewController: UITextViewDelegate {
  func textViewDidBeginEditing(_ textView: UITextView) {
    isUpdated = true
    guard textView.text == placeholderText else { return }
    textView.text = ""
    textView.textColor = .label
  }
  
  func textViewDidEndEditing(_ textView: UITextView) {
    guard textView.text.trimmed().isEmpty else { return }
    textView.text = placeholderText
    textView.textColor = .secondaryLabel
  }
}
