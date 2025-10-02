//
//  AnAddEditPatientViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 20.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnAddEditPatientOutput {
  var onPatientAdded: ((AnPatient) -> Void)? { get set }
  var onPatientUpdated: ((AnPatient) -> Void)? { get set }
  var onDismiss: (() -> Void)? { get set }
  var patient: AnPatient? { get set }
}

final class AnAddEditPatientViewController: AnBaseViewController, AnAddEditPatientOutput {
  
  // MARK: - Output
  
  var onPatientAdded: ((AnPatient) -> Void)?
  var onPatientUpdated: ((AnPatient) -> Void)?
  var onDismiss: (() -> Void)?
  var patient: AnPatient?
  
  // MARK: - Outlets
  
  @IBOutlet internal weak var saveButton: UIBarButtonItem!
  @IBOutlet internal weak var firstNameLabel: UILabel!
  @IBOutlet internal weak var firstNameTextField: UITextField!
  @IBOutlet internal weak var middleNameTextField: UITextField!
  @IBOutlet internal weak var lastNameLabel: UILabel!
  @IBOutlet internal weak var lastNameTextField: UITextField!
  @IBOutlet internal weak var dateOfBirthLabel: UILabel!
  @IBOutlet internal weak var dateOfBirthTextField: UITextField!
  @IBOutlet internal weak var titleButton: UIButton!
  @IBOutlet internal weak var genderButton: UIButton!
  @IBOutlet internal weak var ethnicityButton: UIButton!
  @IBOutlet internal weak var occupationTextField: UITextField!
  @IBOutlet internal weak var phoneLabel: UILabel!
  @IBOutlet internal weak var phoneTextField: UITextField!
  @IBOutlet internal weak var emailLabel: UILabel!
  @IBOutlet internal weak var emailTextField: UITextField!
  @IBOutlet private var notForAddPatientViews: [UIView]!
  
  // MARK: - Private Properties
  
  internal lazy var patientService: AnPatientService = AnAPIService()
  private var isUpdated = false {
    didSet {
      saveButton.isEnabled = isUpdated
    }
  }
  internal var isEditMode: Bool {
    return patient != nil
  }
  
  internal var titleValue: AnPersonTitle?
  internal var genderIdentityValue: AnGenderIdentity?
  internal var ethnicityValue: AnEthnicity?
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureNavigationBar()
    configureBasicUI()
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
    guard validateInput() else { return }
    savePatient()
  }
  
  // MARK: - Private Functions
  
  private func configureNavigationBar() {
    navigationController?.navigationBar.configureAppearance(backgroundColor: .backgroundDefault, removeShadow: false)
    title = isEditMode ?  "Edit Patient" : "Add Patient"
  }
  
  private func configureBasicUI() {
    guard let patient else { return }
    firstNameTextField.text = patient.firstName
    middleNameTextField.text = patient.middleName
    lastNameTextField.text = patient.lastName
    let formattedBirthDate = AnDateFormatter.shared.convert(dateString: patient.birthDate, from: .serverDate, to: .americanDate)
    dateOfBirthTextField.text = formattedBirthDate
    phoneTextField.text = patient.phone
    emailTextField.text = patient.email
  }
  
  private func configureUI() {
    Task {
      
      defer {
        configureButtonsMenu()
        hideHUD()
      }
      
      guard isEditMode,
            let patientId = patient?.id else {
        for view in notForAddPatientViews {
          view.isHidden = true
        }
        return
      }
      
      do {
        showHUD()
        let patientProfile: AnPatient = try await patientService.getPatient(patientId)
        patient = patientProfile
        configureBasicUI()
        titleValue = patient?.title
        genderIdentityValue = patient?.genderIdentity
        ethnicityValue = patient?.ethnicity
        occupationTextField.text = patient?.occupation
      } catch {
        showErrorBanner(error.localizedDescription)
      }
    }
  }
  
  private func configureButtonsMenu() {
    titleButton.configureMenu(withOptions: AnPersonTitle.allCases, current: titleValue, placeholderTitle: "Select Title", clearOption: "None") { [weak self] newValue in
      guard let self else { return }
      isUpdated = true
      titleValue = newValue
    }
    genderButton.configureMenu(withOptions: AnGenderIdentity.allCases, current: genderIdentityValue, placeholderTitle: "Select Gender Identity", clearOption: "None") { [weak self] newValue in
      guard let self else { return }
      isUpdated = true
      genderIdentityValue = newValue
    }
    ethnicityButton.configureMenu(withOptions: AnEthnicity.allCases, current: ethnicityValue, placeholderTitle: "Select Ethnicity", clearOption: "None") { [weak self] newValue in
      guard let self else { return }
      isUpdated = true
      ethnicityValue = newValue
    }
  }
}

// MARK: - UITextFieldDelegate

extension AnAddEditPatientViewController: UITextFieldDelegate {
  func textFieldDidBeginEditing(_ textField: UITextField) {
    isUpdated = true
    if textField == phoneTextField, textField.text?.isEmpty ?? true {
      textField.text = "+1 "
    }
  }
  
  func textFieldDidEndEditing(_ textField: UITextField, reason: UITextField.DidEndEditingReason) {
    guard textField == phoneTextField,
          textField.text?.trimmed() == "+1" else { return }
    textField.text = nil
  }
  
  func textField(_ textField: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
    switch textField {
    case dateOfBirthTextField:
      return formatDateOfBirth(in: textField, range: range, replacementString: string)
    case phoneTextField:
      return formatPhone(in: textField, range: range, replacementString: string)
    default:
      break
    }
    return true
  }
}
